"""Idempotent database seeding and knowledge-source bookkeeping."""
from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path

from . import rag
from .auth import hash_password
from .db import SessionLocal
from .models import Question, Source, Topic, User
from .topics import TOPICS

log = logging.getLogger("ostutor.seed")
QUESTION_BANK = Path(__file__).resolve().parents[1] / "data" / "question_bank.json"
ACCOUNTS = [("student@ostutor.local", "Student123!", "Student", "student"),
            ("faculty@ostutor.local", "Faculty123!", "Faculty", "faculty"),
            ("admin@ostutor.local", "Admin123!", "Administrator", "admin")]


def seed_db() -> None:
    db = SessionLocal()
    try:
        for email, pw, name, role in ACCOUNTS:
            if not db.query(User).filter_by(email=email).first():
                db.add(User(email=email, password_hash=hash_password(pw), name=name, role=role))
        db.commit()
        for name, difficulty, desc, _ in TOPICS:
            t = db.query(Topic).filter_by(name=name).first()
            if t is None:
                db.add(Topic(name=name, description=desc, difficulty=difficulty))
            else:
                t.description, t.difficulty, t.active = desc, difficulty, True
        db.commit()
        admin = db.query(User).filter_by(email="admin@ostutor.local").first()
        if QUESTION_BANK.exists():
            for q in json.loads(QUESTION_BANK.read_text("utf-8")):
                if not db.query(Question).filter_by(prompt=q["prompt"]).first():
                    db.add(Question(topic=q["topic"], difficulty=q["difficulty"], kind=q["kind"], prompt=q["prompt"],
                                    options=q["options"], answer=q["answer"], explanation=q["explanation"],
                                    created_by=admin.id))
            db.commit()
    finally:
        db.close()


def sync_sources() -> None:
    """Mirror files in the documents folder into the Source table with their chunk counts."""
    db = SessionLocal()
    try:
        admin = db.query(User).filter_by(email="admin@ostutor.local").first()
        counts = rag.chunk_counts()
        seen = set()
        for p in sorted(rag.DOCS.rglob("*")):
            if not p.is_file() or p.name.startswith(".") or p.suffix.lower() not in rag.SUPPORTED:
                continue
            rel = str(p.relative_to(rag.DOCS)).replace("\\", "/")
            seen.add(str(p))
            checksum = hashlib.sha256(p.read_bytes()).hexdigest()
            row = db.query(Source).filter_by(path=str(p)).first()
            n = counts.get(rel, 0)
            if row is None:
                db.add(Source(name=p.name, path=str(p), status="ready" if n else "failed", version=1, chunks=n,
                              checksum=checksum, uploaded_by=admin.id if admin else 1))
            else:
                row.checksum, row.chunks, row.status = checksum, n, ("ready" if n else "failed")
        for row in db.query(Source).all():
            if row.path not in seen:
                db.delete(row)
        db.commit()
    except Exception:
        db.rollback()
        log.exception("source sync failed")
    finally:
        db.close()


def run() -> None:  # kept for backwards compatibility with `python -m app.seed`
    seed_db()
    rag.ensure_ready()
    sync_sources()
    print("seed complete", rag.index_status())


if __name__ == "__main__":
    run()
