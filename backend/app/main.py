"""OSTutorLLM API 3.1 - grounded Operating Systems learning platform."""
from __future__ import annotations

import hashlib
import json
import logging
import random
import re
import threading
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.concurrency import run_in_threadpool
from sqlalchemy import Integer, cast, func, text
from sqlalchemy.orm import Session

from . import llm, rag, simulators as sim, tutor
from .auth import current_user, hash_password, require_role, token, verify_password
from .cache import delete_prefix, get_json, key as cache_key, set_json
from .code_runner import run_python, run_shell
from .config import DEFAULT_JWT_SECRET, settings
from .db import Base, SessionLocal, engine, get_db
from .evaluation import aggregate, evaluate_retrieval, metrics as answer_metrics
from .exercises import EXERCISES, public_view
from .grounding import extractive_answer, grounded_validate, strip_unknown_citations, support_report
from .models import (Activity, AuditLog, ChatLog, Conversation, IngestionJob, Message, Progress, Question, Source,
                     Topic, User)
from .ratelimit import RateLimiter
from .schemas import *  # noqa: F401,F403
from .seed import seed_db, sync_sources
from .textproc import salient_terms, tokenize
from .topics import TOPIC_HINTS
from .worker import enqueue_ingestion

VERSION = "3.1.0"
log = logging.getLogger("ostutor")
logging.basicConfig(level=logging.INFO)


def _warm_index() -> None:
    try:
        rag.ensure_ready()
        sync_sources()
        log.info("knowledge base ready: %s", rag.index_status())
    except Exception:
        log.exception("knowledge base warm-up failed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    for attempt in range(10):  # the database container may still be accepting connections
        try:
            Base.metadata.create_all(engine)
            break
        except Exception:
            if attempt == 9:
                raise
            time.sleep(2)
    seed_db()
    if settings.jwt_secret == DEFAULT_JWT_SECRET:
        log.warning("JWT_SECRET is the development default - set a strong secret before exposing this server")
    threading.Thread(target=_warm_index, daemon=True, name="rag-warmup").start()
    yield


app = FastAPI(title="OSTutorLLM", version=VERSION, lifespan=lifespan,
              description="Grounded Operating Systems learning platform: hybrid RAG tutor, simulators, labs, assessments")
_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
_origins += [o.replace("localhost", "127.0.0.1") for o in _origins if "localhost" in o]
app.add_middleware(CORSMiddleware, allow_origins=_origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


@app.exception_handler(ValueError)
async def value_error(request: Request, exc: ValueError):
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    msgs = [f"{'.'.join(str(p) for p in e['loc'][1:]) or 'body'}: {e['msg']}" for e in exc.errors()[:5]]
    return JSONResponse(status_code=422, content={"detail": "; ".join(msgs)})


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    log.exception("unhandled error on %s", request.url.path)
    return JSONResponse(status_code=500, content={"error": "Internal server error", "detail": "Something went wrong on the server. Check the API logs."})


def rate_limit(name: str, max_calls: int, window: int):
    limiter = RateLimiter(max_calls, window)

    def dep(request: Request) -> None:
        ip = request.client.host if request.client else "unknown"
        if not limiter.allow(f"{name}:{ip}"):
            raise HTTPException(429, "Too many requests. Please wait a moment and try again.")
    return dep


login_limit = rate_limit("login", 12, 60)
labs_limit = rate_limit("labs", 40, 60)
FACULTY = require_role("faculty", "admin")


def audit(db: Session, u: User | None, action: str, detail: str = "") -> None:
    db.add(AuditLog(user_id=u.id if u else None, action=action, detail=detail))
    db.commit()


def user_json(u: User) -> dict:
    return {"id": u.id, "email": u.email, "name": u.name, "role": u.role}


# ------------------------------------------------------------------------------------------ health
@app.get("/health")
async def health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    try:
        rag_status = rag.index_status()
    except Exception as exc:
        rag_status = {"ready": False, "error": str(exc)}
    llm_info = await llm.ping()
    return {"status": "ok", "version": VERSION, "database": "ok", "rag": rag_status, "rag_ready": rag_status.get("ready", False),
            "llm": llm_info, "llm_mode": "reachable" if llm_info["reachable"] else "offline-extractive-fallback"}


@app.get("/api/system/status")
async def system_status(u: User = Depends(FACULTY), db: Session = Depends(get_db)):
    return {"version": VERSION, "llm": await llm.ping(max_age=0), "rag": rag.index_status(),
            "settings": {"llm_model": settings.llm_model, "embedding_model": settings.embedding_model,
                         "reranker_model": settings.reranker_model, "chunk_size": rag.CHUNK_SIZE,
                         "chunk_overlap": rag.CHUNK_OVERLAP, "min_coverage": rag.MIN_COVERAGE},
            "counts": {"users": db.query(User).count(), "sources": db.query(Source).count(),
                       "questions": db.query(Question).count(), "conversations": db.query(Conversation).count()}}


# ------------------------------------------------------------------------------------------ auth & profile
@app.post("/api/auth/register")
def register(x: RegisterIn, db: Session = Depends(get_db), _=Depends(login_limit)):
    email = x.email.lower().strip()
    if db.query(User).filter_by(email=email).first():
        raise HTTPException(409, "Email already registered")
    u = User(email=email, name=x.name.strip(), password_hash=hash_password(x.password))
    db.add(u)
    db.commit()
    db.refresh(u)
    return {"access_token": token(u), "user": user_json(u)}


@app.post("/api/auth/login")
def login(x: LoginIn, db: Session = Depends(get_db), _=Depends(login_limit)):
    u = db.query(User).filter_by(email=x.email.lower().strip()).first()
    if not u or not verify_password(x.password, u.password_hash):
        raise HTTPException(401, "Invalid email or password")
    audit(db, u, "login")
    return {"access_token": token(u), "user": user_json(u)}


@app.get("/api/auth/me")
def me(u: User = Depends(current_user)):
    return user_json(u)


@app.put("/api/profile")
def profile(x: ProfileIn, u: User = Depends(current_user), db: Session = Depends(get_db)):
    u.name = x.name.strip()
    db.commit()
    return user_json(u)


# ------------------------------------------------------------------------------------------ topics & progress
@app.get("/api/topics")
def topics(db: Session = Depends(get_db)):
    counts = dict(db.query(Question.topic, func.count(Question.id)).filter_by(kind="mcq", active=True).group_by(Question.topic).all())
    return [{"id": t.id, "name": t.name, "description": t.description, "difficulty": t.difficulty,
             "questions": counts.get(t.name, 0)} for t in db.query(Topic).filter_by(active=True).order_by(Topic.id).all()]


def touch_progress(db: Session, u: User, topic_name: str, score: float, correct: int | None = None) -> float | None:
    t = db.query(Topic).filter_by(name=topic_name).first()
    if not t:
        return None
    p = db.query(Progress).filter_by(user_id=u.id, topic_id=t.id).first()
    if p is None:
        p = Progress(user_id=u.id, topic_id=t.id, mastery=0, attempts=0, correct=0)
        db.add(p)
    p.mastery = round(score if not p.attempts else p.mastery * 0.7 + score * 0.3, 2)
    p.attempts = (p.attempts or 0) + 1
    p.correct = (p.correct or 0) + (correct if correct is not None else (1 if score >= 60 else 0))
    return p.mastery


def recommendation(mastery: float) -> str:
    if mastery < 60:
        return "Review this topic with the tutor, then retry the quiz"
    return "Practice harder questions" if mastery < 80 else "Move on to the next topic"


@app.get("/api/dashboard")
def dashboard(u: User = Depends(current_user), db: Session = Depends(get_db)):
    prog = {p.topic_id: p for p in db.query(Progress).filter_by(user_id=u.id).all()}
    rows = []
    for t in db.query(Topic).filter_by(active=True).order_by(Topic.id).all():
        p = prog.get(t.id)
        rows.append({"topic_id": t.id, "name": t.name, "difficulty": t.difficulty, "mastery": round(p.mastery, 1) if p else 0,
                     "attempts": p.attempts if p else 0, "correct": p.correct if p else 0})
    attempted = [r for r in rows if r["attempts"]]
    acts = db.query(Activity).filter_by(user_id=u.id).order_by(Activity.created_at.desc()).limit(40).all()
    days = {a.created_at.date() for a in acts}
    streak, day = 0, datetime.utcnow().date()
    if day not in days:
        day -= timedelta(days=1)
    while day in days:
        streak += 1
        day -= timedelta(days=1)
    weakest = sorted(attempted, key=lambda r: r["mastery"])[:3]
    return {"overall": round(sum(r["mastery"] for r in attempted) / len(attempted), 1) if attempted else 0, "topics": rows,
            "attempted": len(attempted), "streak_days": streak, "weakest": weakest,
            "next_topic": (weakest[0]["name"] if weakest else (rows[0]["name"] if rows else None)),
            "activity": [{"kind": a.kind, "topic": a.topic, "score": a.score, "created_at": a.created_at.isoformat()} for a in acts[:20]]}


@app.post("/api/progress")
def progress(x: ProgressIn, u: User = Depends(current_user), db: Session = Depends(get_db)):
    mastery = touch_progress(db, u, x.topic, x.score)
    if mastery is None:
        raise HTTPException(404, "Topic not found")
    db.add(Activity(user_id=u.id, kind=x.activity, topic=x.topic, score=x.score))
    db.commit()
    return {"mastery": mastery, "recommendation": recommendation(mastery)}


# ------------------------------------------------------------------------------------------ tutor
def _citations(hits: list[dict]) -> list[dict]:
    return [{"id": f"S{i + 1}", "source": h["source"], "path": h["path"], "title": h.get("title", ""), "section": h.get("section", ""),
             "page": h.get("page", 1), "chunk": h["chunk"], "score": h["score"], "scores": h.get("scores", {}),
             "type": h["type"], "text": h["text"]} for i, h in enumerate(hits)]


def prepare_chat(x: ChatIn, u: User, db: Session) -> dict:
    if x.conversation_id:
        conv = db.get(Conversation, x.conversation_id)
        if not conv or conv.user_id != u.id:
            raise HTTPException(404, "Conversation not found")
    else:
        conv = Conversation(user_id=u.id, title=x.message.strip()[:60], topic=x.topic)
        db.add(conv)
        db.commit()
        db.refresh(conv)
    past = db.query(Message).filter_by(conversation_id=conv.id).order_by(Message.id.desc()).limit(6).all()
    history = [{"role": m.role, "content": m.content} for m in reversed(past)]
    query = tutor.contextualize(x.message, history)
    res = rag.search(query, k=settings.rag_final_k, topic_hint=TOPIC_HINTS.get(x.topic or ""), use_reranker=x.use_reranker)
    hits, meta = res["hits"], res["meta"]
    if not meta.get("ready"):
        raise HTTPException(503, "The knowledge base has no indexed sources yet. Add course material and rebuild the index.")
    mastery = 0.0
    if x.topic:
        t = db.query(Topic).filter_by(name=x.topic).first()
        p = db.query(Progress).filter_by(user_id=u.id, topic_id=t.id).first() if t else None
        mastery = round(p.mastery, 1) if p else 0.0
    abstain = bool(meta["abstain"] or not hits)
    return {"question": x.message, "topic": x.topic, "mode_name": x.mode, "difficulty": x.difficulty, "user_id": u.id,
            "conversation_id": conv.id, "hits": hits, "citations": _citations(hits), "meta": meta, "abstain": abstain,
            "messages": tutor.build_messages(x.message, hits, x.mode, x.difficulty, x.topic, mastery, history)}


def finalize(ctx: dict, answer: str, latency: float, mode: str, db: Session) -> dict:
    hits, citations = ctx["hits"], ctx["citations"]
    answer = strip_unknown_citations(answer, len(citations))
    support = support_report(answer, hits) if hits and mode != "abstain" else {"sentences": [], "support_score": 0, "supported_ratio": 0, "citation_ratio": 0}
    grounded = bool(mode != "abstain" and citations and grounded_validate(answer, citations, hits))
    suggestions = tutor.suggestions(hits, ctx["question"]) if mode != "abstain" else []
    model_name = settings.llm_model if mode == "llm" else ("extractive-fallback" if mode == "extractive" else "none")
    conv = db.get(Conversation, ctx["conversation_id"])
    conv.updated_at = datetime.utcnow()
    db.add(Message(conversation_id=conv.id, role="user", content=ctx["question"], meta={"mode": ctx["mode_name"], "topic": ctx["topic"]}))
    reply = Message(conversation_id=conv.id, role="assistant", content=answer, citations=citations if mode != "abstain" else [],
                    meta={"grounded": grounded, "mode": mode, "model": model_name, "latency_ms": latency,
                          "support_score": support["support_score"], "suggestions": suggestions,
                          "confidence": ctx["meta"]["confidence"]})
    db.add(reply)
    db.add(ChatLog(user_id=ctx["user_id"], question=ctx["question"], answer=answer, citations=citations, grounded=grounded, latency_ms=latency))
    db.add(Activity(user_id=ctx["user_id"], kind="tutor", topic=ctx["topic"] or "Operating Systems", score=0))
    db.commit()
    db.refresh(reply)
    return {"answer": answer, "citations": citations if mode != "abstain" else [], "grounded": grounded, "support": support,
            "suggestions": suggestions, "conversation_id": conv.id, "message_id": reply.id, "latency_ms": latency,
            "retrieved": len(hits), "retrieval": ctx["meta"], "model": model_name, "mode": mode,
            "abstained": mode == "abstain", "confidence": ctx["meta"]["confidence"]}


def _extractive(ctx: dict) -> str:
    text_, _ = extractive_answer(ctx["question"], ctx["hits"])
    return text_ or tutor.abstain_message(ctx["question"])


@app.post("/api/tutor/chat")
async def tutor_chat(x: ChatIn, u: User = Depends(current_user), db: Session = Depends(get_db)):
    ctx = await run_in_threadpool(prepare_chat, x, u, db)
    if ctx["abstain"]:
        return finalize(ctx, tutor.abstain_message(x.message), 0.0, "abstain", db)
    gen_key = cache_key("gen", {"m": ctx["messages"], "model": settings.llm_model})
    cached = get_json(gen_key)
    started = time.perf_counter()
    answer, latency = (cached["answer"], 0.0) if cached else await llm.generate(ctx["messages"])
    if answer:
        if not cached:
            set_json(gen_key, {"answer": answer}, settings.cache_ttl_seconds)
        return finalize(ctx, answer, latency, "llm", db)
    return finalize(ctx, _extractive(ctx), round((time.perf_counter() - started) * 1000, 2), "extractive", db)


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


@app.post("/api/tutor/stream")
async def tutor_stream(x: ChatIn, u: User = Depends(current_user), db: Session = Depends(get_db)):
    ctx = await run_in_threadpool(prepare_chat, x, u, db)  # all request-scoped DB work happens before the stream starts

    async def events():
        yield _sse("meta", {"conversation_id": ctx["conversation_id"], "citations": ctx["citations"], "retrieval": ctx["meta"],
                            "abstain": ctx["abstain"]})
        started = time.perf_counter()
        mode, answer = "llm", ""
        if ctx["abstain"]:
            mode, answer = "abstain", tutor.abstain_message(ctx["question"])
            yield _sse("token", {"text": answer})
        else:
            parts: list[str] = []
            try:
                async for delta in llm.stream(ctx["messages"]):
                    parts.append(delta)
                    yield _sse("token", {"text": delta})
            except llm.LLMError:
                pass
            answer = "".join(parts).strip()
            if not answer:
                mode, answer = "extractive", _extractive(ctx)
                yield _sse("replace", {"text": answer})
        latency = round((time.perf_counter() - started) * 1000, 2)
        with SessionLocal() as s2:
            try:
                yield _sse("done", finalize(ctx, answer, latency, mode, s2))
            except Exception:
                log.exception("failed to persist streamed answer")
                yield _sse("error", {"detail": "The answer was generated but could not be saved."})

    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/api/tutor/conversations")
def conversations(u: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.query(Conversation).filter_by(user_id=u.id).order_by(Conversation.updated_at.desc()).limit(50).all()
    return [{"id": c.id, "title": c.title, "topic": c.topic, "updated_at": c.updated_at.isoformat()} for c in rows]


@app.get("/api/tutor/conversations/{cid}")
def conversation(cid: int, u: User = Depends(current_user), db: Session = Depends(get_db)):
    c = db.get(Conversation, cid)
    if not c or c.user_id != u.id:
        raise HTTPException(404, "Conversation not found")
    msgs = db.query(Message).filter_by(conversation_id=cid).order_by(Message.id).all()
    return {"id": c.id, "title": c.title, "topic": c.topic,
            "messages": [{"id": m.id, "role": m.role, "content": m.content, "citations": m.citations, "meta": m.meta,
                          "feedback": m.feedback} for m in msgs]}


@app.delete("/api/tutor/conversations/{cid}")
def delete_conversation(cid: int, u: User = Depends(current_user), db: Session = Depends(get_db)):
    c = db.get(Conversation, cid)
    if not c or c.user_id != u.id:
        raise HTTPException(404, "Conversation not found")
    db.query(Message).filter_by(conversation_id=cid).delete()
    db.delete(c)
    db.commit()
    return {"ok": True}


@app.post("/api/tutor/messages/{mid}/feedback")
def message_feedback(mid: int, x: FeedbackIn, u: User = Depends(current_user), db: Session = Depends(get_db)):
    m = db.get(Message, mid)
    conv = db.get(Conversation, m.conversation_id) if m else None
    if not m or not conv or conv.user_id != u.id or m.role != "assistant":
        raise HTTPException(404, "Message not found")
    m.feedback = None if m.feedback == x.value else x.value
    db.commit()
    return {"id": m.id, "feedback": m.feedback}


# ------------------------------------------------------------------------------------------ retrieval lab
@app.post("/api/rag/search")
def rag_search(x: SearchIn, u: User = Depends(current_user)):
    res = rag.search(x.query, k=x.k, filters={"source": x.source} if x.source else None, use_reranker=x.use_reranker)
    return {"hits": [{k: v for k, v in h.items() if k != "checksum"} for h in res["hits"]], "meta": res["meta"]}


@app.get("/api/rag/status")
def rag_status(u: User = Depends(current_user)):
    return rag.index_status()


# ------------------------------------------------------------------------------------------ assessments
@app.post("/api/quizzes/generate")
def quiz(x: QuizIn, u: User = Depends(current_user), db: Session = Depends(get_db)):
    pool = db.query(Question).filter_by(topic=x.topic, kind=x.kind, active=True).all()
    same = [q for q in pool if x.difficulty in ("any", q.difficulty)]
    pool = same if len(same) >= min(x.count, len(pool)) and same else pool
    if not pool:
        raise HTTPException(404, f"No {x.kind} questions exist for {x.topic} yet")
    picked = random.sample(pool, min(x.count, len(pool)))
    return {"topic": x.topic, "kind": x.kind, "mode": "question-bank",
            "assessment": [{"id": q.id, "question": q.prompt, "options": q.options, "difficulty": q.difficulty, "kind": q.kind} for q in picked]}


@app.post("/api/quizzes/score")
def score_quiz(x: QuizScoreIn, u: User = Depends(current_user), db: Session = Depends(get_db)):
    ids = [int(i) for i in x.answers if str(i).isdigit()]
    qs = {q.id: q for q in db.query(Question).filter(Question.id.in_(ids), Question.kind == "mcq").all()} if ids else {}
    if not qs:
        raise HTTPException(422, "No valid answers were submitted")
    results, correct = [], 0
    for qid, q in qs.items():
        given = str(x.answers.get(str(qid), "")).strip().upper()
        ok = given == q.answer.strip().upper()
        correct += ok
        results.append({"id": qid, "correct": ok, "given": given, "answer": q.answer, "explanation": q.explanation})
    score = round(100 * correct / len(qs), 1)
    mastery = touch_progress(db, u, x.topic, score, correct)
    db.add(Activity(user_id=u.id, kind="quiz", topic=x.topic, score=score, payload={"count": len(qs)}))
    db.commit()
    return {"score": score, "correct": correct, "total": len(qs), "results": results, "mastery": mastery,
            "recommendation": recommendation(score if mastery is None else mastery)}


@app.post("/api/quizzes/viva-grade")
def viva_grade(x: VivaIn, u: User = Depends(current_user), db: Session = Depends(get_db)):
    q = db.get(Question, x.question_id)
    if not q or q.kind != "viva":
        raise HTTPException(404, "Viva question not found")
    gold, got = salient_terms(q.answer), set(tokenize(x.answer))
    covered = sorted(gold & got)
    missing = sorted(gold - got)
    score = round(100 * len(covered) / len(gold), 1) if gold else 0.0
    mastery = touch_progress(db, u, q.topic, score)
    db.add(Activity(user_id=u.id, kind="viva", topic=q.topic, score=score))
    db.commit()
    verdict = "Strong answer" if score >= 70 else ("Partly there - compare with the model answer" if score >= 40 else "Needs work - read the model answer")
    return {"score": score, "verdict": verdict, "model_answer": q.answer, "covered_terms": covered, "missing_terms": missing[:12], "mastery": mastery}


# ------------------------------------------------------------------------------------------ knowledge base admin
def reindex_async(db: Session) -> dict:
    try:
        job = enqueue_ingestion(db)
        return {"job_id": job.id, "status": "queued"}
    except Exception:  # Redis unavailable: index in-process so uploads still work
        log.warning("job queue unavailable; indexing in a background thread")
        threading.Thread(target=_warm_reindex, daemon=True).start()
        return {"job_id": None, "status": "processing"}


def _warm_reindex() -> None:
    try:
        rag.ingest_all()
        sync_sources()
    except Exception:
        log.exception("background reindex failed")


@app.get("/api/sources")
def sources(u: User = Depends(FACULTY), db: Session = Depends(get_db)):
    return [{"id": s.id, "name": s.name, "path": s.path, "status": s.status, "version": s.version, "chunks": s.chunks,
             "checksum": s.checksum, "created_at": s.created_at.isoformat()} for s in db.query(Source).order_by(Source.id).all()]


@app.post("/api/sources/upload")
async def upload(file: UploadFile = File(...), u: User = Depends(FACULTY), db: Session = Depends(get_db)):
    raw_name = (file.filename or "").replace("\\", "/").split("/")[-1]
    ext = "." + raw_name.rsplit(".", 1)[-1].lower() if "." in raw_name else ""
    if ext not in {".pdf", ".pptx", ".docx", ".txt", ".md"}:
        raise HTTPException(400, "Supported source types: PDF, PPTX, DOCX, TXT, MD")
    data = await file.read()
    if len(data) > 15 * 1024 * 1024:
        raise HTTPException(413, "Source file exceeds the 15 MB limit")
    stem = re.sub(r"[^A-Za-z0-9._ -]+", "_", raw_name.rsplit(".", 1)[0])[:80].strip(" ._") or "source"
    path = rag.DOCS / (stem + ext)
    path.write_bytes(data)
    try:
        has_text = bool(rag.extract(path).strip())
    except Exception:
        has_text = False
    if not has_text:
        path.unlink(missing_ok=True)
        raise HTTPException(400, "The file could not be read or contains no extractable text")
    checksum = hashlib.sha256(data).hexdigest()
    row = db.query(Source).filter_by(path=str(path)).first()
    if row is None:
        row = Source(name=path.name, path=str(path), status="queued", version=1, chunks=0, checksum=checksum, uploaded_by=u.id)
        db.add(row)
    else:
        row.version, row.checksum, row.status = row.version + 1, checksum, "queued"
    db.commit()
    audit(db, u, "source.upload", path.name)
    delete_prefix("gen")
    return {"ok": True, "source": path.name, "message": "Indexing started in the background.", **reindex_async(db)}


@app.delete("/api/sources/{sid}")
def delete_source(sid: int, u: User = Depends(FACULTY), db: Session = Depends(get_db)):
    s = db.get(Source, sid)
    if not s:
        raise HTTPException(404, "Source not found")
    from pathlib import Path

    Path(s.path).unlink(missing_ok=True)
    db.delete(s)
    db.commit()
    audit(db, u, "source.delete", s.name)
    delete_prefix("gen")
    return {"ok": True, **reindex_async(db)}


@app.post("/api/rag/rebuild")
def rebuild(u: User = Depends(FACULTY), db: Session = Depends(get_db)):
    delete_prefix("gen")
    return {"ok": True, "sources": db.query(Source).count(), **reindex_async(db)}


@app.get("/api/rag/jobs/{job_id}")
def rag_job(job_id: int, u: User = Depends(FACULTY), db: Session = Depends(get_db)):
    job = db.get(IngestionJob, job_id)
    if not job:
        raise HTTPException(404, "Ingestion job not found")
    return {"id": job.id, "status": job.status, "result": job.result, "error": job.error,
            "created_at": job.created_at.isoformat(), "updated_at": job.updated_at.isoformat()}


@app.get("/api/admin/analytics")
def admin_analytics(u: User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    chats = db.query(func.count(ChatLog.id), func.avg(ChatLog.latency_ms), func.avg(cast(ChatLog.grounded, Integer))).first()
    return {"users": db.query(User).count(), "sources": db.query(Source).count(), "questions": db.query(Question).count(),
            "activities": db.query(Activity).count(), "chat_sessions": chats[0] or 0,
            "avg_latency_ms": round(float(chats[1] or 0), 1), "grounded_rate": round(float(chats[2] or 0), 3),
            "thumbs_up": db.query(Message).filter_by(feedback=1).count(), "thumbs_down": db.query(Message).filter_by(feedback=-1).count(),
            "rag_chunks": rag.index_status()["chunks"]}


@app.get("/api/admin/students")
def students(u: User = Depends(FACULTY), db: Session = Depends(get_db)):
    avg = dict(db.query(Progress.user_id, func.avg(Progress.mastery)).group_by(Progress.user_id).all())
    return [{"id": x.id, "name": x.name, "email": x.email, "role": x.role, "mastery": round(float(avg.get(x.id) or 0), 1)}
            for x in db.query(User).order_by(User.id).all()]


# ------------------------------------------------------------------------------------------ simulators
@app.post("/api/simulators/cpu")
def cpu(x: CPUIn):
    return sim.cpu_scheduling(x.algorithm, x.processes, x.quantum)


@app.post("/api/simulators/cpu/compare")
def cpu_compare(x: CompareIn):
    return sim.cpu_compare(x.processes, x.quantum)


@app.post("/api/simulators/page-replacement")
def page(x: PageIn):
    return sim.page_replacement(x.algorithm, x.reference_string, x.frames)


@app.post("/api/simulators/page-replacement/compare")
def page_compare(x: PageCompareIn):
    return sim.page_compare(x.reference_string, x.frames)


@app.post("/api/simulators/banker")
def banker(x: BankerIn):
    return sim.bankers(x.allocation, x.maximum, x.available, x.request)


@app.post("/api/simulators/deadlock")
def deadlock(x: DeadlockIn):
    return sim.deadlock_detection(x.allocation, x.request, x.available)


@app.post("/api/simulators/disk")
def disk(x: DiskIn):
    return sim.disk_scheduling(x.algorithm, x.requests, x.head, x.disk_size, x.direction)


@app.post("/api/simulators/producer-consumer")
def producer(x: SyncIn):
    return sim.producer_consumer(x.buffer_size, x.items, x.producer_period, x.consumer_period)


@app.post("/api/simulators/dining-philosophers")
def dining(x: DiningIn | None = None):
    x = x or DiningIn()
    return sim.dining_philosophers(x.n, x.strategy, x.meals)


@app.post("/api/simulators/paging")
def paging_api(x: PagingIn):
    return sim.paging(x.addresses, x.page_size, x.num_frames, x.tlb_size)


@app.post("/api/simulators/segmentation")
def seg_api(x: SegIn):
    return sim.segmentation(x.segments, x.logical)


@app.post("/api/simulators/threads")
def threads_api(x: ThreadsIn | None = None):
    x = x or ThreadsIn()
    return sim.thread_lifecycle(x.scenario, x.quantum)


# ------------------------------------------------------------------------------------------ labs
@app.get("/api/labs/exercises")
def exercises(u: User = Depends(current_user)):
    return [public_view(e) for e in EXERCISES]


@app.post("/api/labs/shell")
def shell(x: ShellIn, u: User = Depends(current_user), _=Depends(labs_limit)):
    return run_shell(x.script, settings.max_code_seconds)


@app.post("/api/labs/python")
def py(x: PythonIn, u: User = Depends(current_user), _=Depends(labs_limit)):
    return run_python(x.source, settings.max_code_seconds)


@app.post("/api/labs/test")
def test_code(x: CodeTestIn, u: User = Depends(current_user), db: Session = Depends(get_db), _=Depends(labs_limit)):
    ex = next((e for e in EXERCISES if e["id"] == x.exercise_id), None) if x.exercise_id else None
    if x.exercise_id and not ex:
        raise HTTPException(404, "Exercise not found")
    language, expected = (ex["language"], ex["expected_stdout"]) if ex else (x.language, x.expected_stdout)
    out = (run_python if language == "python" else run_shell)(x.source, settings.max_code_seconds)
    passed = bool(out["ok"] and out["stdout"].strip() == expected.strip())
    if passed and ex:
        touch_progress(db, u, ex["topic"], 100, 1)
        db.add(Activity(user_id=u.id, kind="lab", topic=ex["topic"], score=100, payload={"exercise": ex["id"]}))
        db.commit()
    return {"passed": passed, "actual_stdout": out["stdout"], "stderr": out["stderr"], "exit_code": out["exit_code"],
            "expected_stdout": expected, "duration_ms": out["duration_ms"], "hint": (ex or {}).get("hint") if not passed else None}


# ------------------------------------------------------------------------------------------ evaluation
def _benchmark() -> list[dict]:
    return json.loads((rag.DATA / "benchmarks" / "os_questions.json").read_text("utf-8"))


@app.post("/api/evaluation/retrieval")
def evaluate_retrieval_api(u: User = Depends(FACULTY)):
    result = evaluate_retrieval(_benchmark(), lambda q, k: rag.search(q, k=k), 5)
    result["index"] = rag.index_status()
    return result


@app.post("/api/evaluation/run")
async def evaluate(limit: int = 10, u: User = Depends(FACULTY)):
    rows = []
    for item in [b for b in _benchmark() if not b.get("out_of_scope")][: max(1, min(limit, 40))]:
        res = rag.search(item["question"], k=5)
        hits = res["hits"]
        messages = tutor.build_messages(item["question"], hits, "exam", "medium")
        answer, latency = await llm.generate(messages)
        mode = "llm"
        if not answer:
            mode, (answer, _) = "extractive", extractive_answer(item["question"], hits)
        answer = strip_unknown_citations(answer or "", len(hits))
        rows.append({"id": item["id"], "query": item["question"], "answer_mode": mode, "latency_ms": latency,
                     **answer_metrics(answer, hits, item.get("gold_concepts", [])),
                     "support_score": support_report(answer, hits)["support_score"]})
    keys = ["citation_correctness", "groundedness", "hallucination_rate_proxy", "concept_coverage", "support_score"]
    return {"benchmark_size": len(rows), "model": settings.llm_model, "embedding_model": settings.embedding_model,
            "reranker_model": settings.reranker_model, "cases": rows, "aggregate": aggregate(rows, keys),
            "llm_cases": sum(1 for r in rows if r["answer_mode"] == "llm")}


@app.get("/api/openapi-summary")
def api_summary():
    return {"docs": "/docs", "health": "/health", "version": VERSION,
            "features": ["Two-phase hybrid RAG (BM25 + TF-IDF now, BGE + FAISS when ready)", "Heading-aware chunking with section citations",
                         "Glossary query expansion, RRF fusion, cross-encoder rerank, MMR diversification",
                         "Evidence-coverage abstention", "Streaming tutor with per-sentence grounding report",
                         "Persistent conversations and answer feedback", "Server-side quiz scoring and viva grading",
                         "Step-through OS simulators", "Sandboxed Python and shell labs with auto-graded exercises",
                         "Retrieval and answer evaluation", "Ollama or any OpenAI-compatible LLM, fine-tune ready"]}
