"""Hybrid retrieval engine for the OS knowledge base.

Pipeline
    documents -> heading-aware chunks -> sparse index (BM25 + TF-IDF uni/bigram) [phase 1, instant]
                                      -> dense embeddings (BGE) + FAISS            [phase 2, background]
    query -> glossary expansion -> sparse + dense candidates -> weighted RRF
          -> optional cross-encoder rerank -> MMR diversification -> evidence-coverage confidence

The sparse phase needs no model download, so the tutor answers immediately after start-up and
silently upgrades to hybrid retrieval once embeddings are ready.
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import threading
import time
from pathlib import Path

import numpy as np
from scipy import sparse as sp

from .textproc import expand_query, salient_terms, tokenize

log = logging.getLogger("ostutor.rag")


def _data_dir() -> Path:
    env = os.getenv("OSTUTOR_DATA_DIR")
    if env:
        return Path(env)
    if Path("/app/data").exists():
        return Path("/app/data")
    return Path(__file__).resolve().parents[1] / "data"


def _num(name: str, default, cast=int):
    try:
        return cast(os.getenv(name, default))
    except (TypeError, ValueError):
        return cast(default)


DATA = _data_dir()
DOCS = DATA / "documents"
INDEX = DATA / "index"
DOCS.mkdir(parents=True, exist_ok=True)
INDEX.mkdir(parents=True, exist_ok=True)

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-large-en-v1.5")
RERANKER_MODEL = os.getenv("RERANKER_MODEL", "BAAI/bge-reranker-base")
TOP_DENSE = _num("RAG_DENSE_K", 24)
TOP_SPARSE = _num("RAG_SPARSE_K", 24)
RERANK_K = _num("RAG_RERANK_K", 12)
CHUNK_SIZE = _num("RAG_CHUNK_SIZE", 900)
CHUNK_OVERLAP = _num("RAG_CHUNK_OVERLAP", 120)
MIN_COVERAGE = _num("RAG_MIN_COVERAGE", 0.4, float)
MMR_LAMBDA = _num("RAG_MMR_LAMBDA", 0.72, float)
INDEX_VERSION = 3
SUPPORTED = {".md", ".markdown", ".txt", ".pdf", ".docx", ".pptx"}
BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


def test_mode() -> bool:
    return os.getenv("OSTUTOR_TEST_MODE", "0").lower() in {"1", "true", "yes", "on"}


# --------------------------------------------------------------------------- extraction
def _extract_pages(path: Path) -> list[dict]:
    s = path.suffix.lower()
    if s in {".md", ".markdown", ".txt"}:
        return [{"page": 1, "markdown": s != ".txt", "text": path.read_text(encoding="utf-8", errors="ignore")}]
    if s == ".pdf":
        from pypdf import PdfReader

        return [
            {"page": i + 1, "markdown": False, "text": p.extract_text() or ""}
            for i, p in enumerate(PdfReader(str(path)).pages)
        ]
    if s == ".docx":
        from docx import Document

        lines = []
        for p in Document(str(path)).paragraphs:
            if not p.text.strip():
                continue
            style = (p.style.name or "") if p.style is not None else ""
            if style == "Title":
                lines.append("# " + p.text.strip())
            elif style.startswith("Heading "):
                try:
                    lines.append("#" * max(1, min(6, int(style.split()[-1]))) + " " + p.text.strip())
                except ValueError:
                    lines.append(p.text.strip())
            else:
                lines.append(p.text.strip())
        return [{"page": 1, "markdown": True, "text": "\n\n".join(lines)}]
    if s == ".pptx":
        from pptx import Presentation

        out = []
        for i, slide in enumerate(Presentation(str(path)).slides):
            title_shape = slide.shapes.title
            title = title_shape.text.strip() if title_shape is not None and title_shape.has_text_frame else ""
            body = [
                sh.text_frame.text.strip()
                for sh in slide.shapes
                if sh.has_text_frame and sh is not title_shape and sh.text_frame.text.strip()
            ]
            text = (f"# {title}\n\n" if title else "") + "\n\n".join(body)
            out.append({"page": i + 1, "markdown": True, "text": text})
        return out
    return []


def extract(path: Path) -> str:
    return "\n".join(p["text"] for p in _extract_pages(path))


# --------------------------------------------------------------------------- chunking
def _heading(line: str):
    s = line.strip()
    if not s.startswith("#"):
        return None
    level = len(s) - len(s.lstrip("#"))
    if level > 6 or len(s) <= level or s[level] != " ":
        return None
    return level, s[level:].strip().rstrip("#").strip()


def _sections(text: str, markdown: bool) -> list[tuple[list[str], str]]:
    """Split text into (heading path, body) sections. Non-markdown text is one section."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if not markdown:
        return [([], text.strip())] if text.strip() else []
    out: list[tuple[list[str], str]] = []
    path: list[str] = []
    buf: list[str] = []
    in_code = False
    for line in text.split("\n"):
        if line.strip().startswith("```"):
            in_code = not in_code
        m = None if in_code else _heading(line)
        if m:
            body = "\n".join(buf).strip()
            if body:
                out.append((list(path), body))
            buf = []
            level, title = m
            path = path[: level - 1] + [title]
        else:
            buf.append(line)
    body = "\n".join(buf).strip()
    if body:
        out.append((list(path), body))
    return out


def _split_long(paragraph: str, size: int) -> list[str]:
    from .textproc import sentences

    pieces, cur = [], ""
    for sent in sentences(paragraph) or [paragraph]:
        while len(sent) > size:  # a single enormous sentence: split on whitespace
            cut = sent.rfind(" ", 0, size)
            cut = cut if cut > size // 2 else size
            if cur:
                pieces.append(cur)
                cur = ""
            pieces.append(sent[:cut].strip())
            sent = sent[cut:].strip()
        if not cur:
            cur = sent
        elif len(cur) + 1 + len(sent) <= size:
            cur += " " + sent
        else:
            pieces.append(cur)
            cur = sent
    if cur:
        pieces.append(cur)
    return pieces


def pack(body: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    paras = [p.strip() for p in body.split("\n\n") if p.strip()]
    units: list[str] = []
    for p in paras:
        units.extend([p] if len(p) <= size else _split_long(p, size))
    chunks: list[str] = []
    cur = ""
    for u in units:
        if not cur:
            cur = u
        elif len(cur) + 2 + len(u) <= size:
            cur += "\n\n" + u
        else:
            chunks.append(cur)
            cur = u
    if cur:
        chunks.append(cur)
    if overlap > 0 and len(chunks) > 1:
        merged = [chunks[0]]
        for prev, nxt in zip(chunks, chunks[1:]):
            tail = prev[-overlap:]
            tail = tail[tail.find(" ") + 1:] if " " in tail else tail
            merged.append((tail + " " + nxt).strip())
        chunks = merged
    return chunks


def build_rows() -> tuple[list[dict], list[dict]]:
    rows: list[dict] = []
    skipped: list[dict] = []
    for p in sorted(DOCS.rglob("*")):
        if not p.is_file() or p.name.startswith(".") or p.suffix.lower() not in SUPPORTED:
            continue
        rel = str(p.relative_to(DOCS)).replace("\\", "/")
        try:
            raw = p.read_bytes()
            pages = _extract_pages(p)
        except Exception as exc:  # a corrupt upload must not break the whole index
            skipped.append({"path": rel, "error": str(exc)[:200]})
            continue
        checksum = hashlib.sha256(raw).hexdigest()
        title = p.stem.replace("_", " ")
        first = _sections(pages[0]["text"], pages[0]["markdown"]) if pages else []
        if first and first[0][0]:
            title = first[0][0][0]
        n = 0
        for page in pages:
            for path_list, body in _sections(page["text"], page["markdown"]):
                parts = (path_list[1:] or path_list[:1]) if path_list and path_list[0] == title else path_list
                section = " › ".join(parts)
                for piece in pack(body):
                    rows.append({
                        "id": f"{rel}#{n}", "text": piece, "source": p.name, "path": rel, "chunk": n,
                        "checksum": checksum, "type": p.suffix.lower()[1:], "page": page["page"],
                        "section": section, "title": title,
                    })
                    n += 1
    return rows, skipped


def _index_text(row: dict) -> str:
    head = ". ".join(x for x in (row.get("title"), row.get("section")) if x)
    return f"{head}.\n{row['text']}" if head else row["text"]


def corpus_fingerprint() -> str:
    h = hashlib.sha256()
    h.update(f"v{INDEX_VERSION}|{CHUNK_SIZE}|{CHUNK_OVERLAP}".encode())
    for p in sorted(DOCS.rglob("*")):
        if p.is_file() and not p.name.startswith(".") and p.suffix.lower() in SUPPORTED:
            h.update(str(p.relative_to(DOCS)).encode())
            h.update(hashlib.sha256(p.read_bytes()).digest())
    return h.hexdigest()


# --------------------------------------------------------------------------- sparse index
def _csr(token_lists: list[list[str]], vocab: dict[str, int]) -> sp.csr_matrix:
    indptr, indices, data = [0], [], []
    for toks in token_lists:
        counts: dict[int, int] = {}
        for t in toks:
            j = vocab.get(t)
            if j is not None:
                counts[j] = counts.get(j, 0) + 1
        for j in sorted(counts):
            indices.append(j)
            data.append(counts[j])
        indptr.append(len(indices))
    return sp.csr_matrix(
        (np.asarray(data, dtype=np.float32), np.asarray(indices, dtype=np.int32), np.asarray(indptr, dtype=np.int32)),
        shape=(len(token_lists), len(vocab)),
    )


def _vocab(token_lists: list[list[str]]) -> dict[str, int]:
    return {t: i for i, t in enumerate(sorted({t for toks in token_lists for t in toks}))}


def _bigrams(toks: list[str]) -> list[str]:
    return [a + "_" + b for a, b in zip(toks, toks[1:])]


class Sparse:
    """BM25 over unigrams plus sublinear TF-IDF over unigrams and bigrams (phrase signal)."""

    def __init__(self, texts: list[str], k1: float = 1.5, b: float = 0.75):
        uni = [tokenize(t) for t in texts]
        n = len(texts)
        self.vocab = _vocab(uni)
        tf = _csr(uni, self.vocab)
        df = np.bincount(tf.indices, minlength=len(self.vocab))
        self.idf = np.log(1 + (n - df + 0.5) / (df + 0.5)).astype(np.float32)
        dl = np.asarray(tf.sum(axis=1)).ravel()
        avgdl = max(float(dl.mean()) if n else 1.0, 1e-9)
        rows = np.repeat(np.arange(n), np.diff(tf.indptr))
        w = tf.copy()
        w.data = self.idf[w.indices] * w.data * (k1 + 1) / (w.data + k1 * (1 - b + b * dl[rows] / avgdl))
        self.bm25 = w.tocsr()

        both = [u + _bigrams(u) for u in uni]
        self.vocab2 = _vocab(both)
        tf2 = _csr(both, self.vocab2)
        df2 = np.bincount(tf2.indices, minlength=len(self.vocab2))
        self.idf2 = (np.log((1 + n) / (1 + df2)) + 1).astype(np.float32)
        x = tf2.copy()
        x.data = (1 + np.log(x.data)) * self.idf2[x.indices]
        norms = np.sqrt(np.asarray(x.multiply(x).sum(axis=1)).ravel())
        self.tfidf = (sp.diags(1.0 / np.maximum(norms, 1e-9)) @ x).tocsr()

    def term_idf(self, term: str) -> float:
        """IDF of a stemmed term; terms never seen in the corpus get the maximum (they are the most informative)."""
        j = self.vocab.get(term)
        if j is not None:
            return float(self.idf[j])
        return float(np.log(1 + (self.bm25.shape[0] + 0.5) / 0.5))

    def scores(self, query_tokens: list[str], extra_tokens: list[str] | None = None,
               extra_weight: float = 0.4) -> tuple[np.ndarray, np.ndarray]:
        """Score all documents. Expansion terms (extra_tokens) count for less than the user's own words."""
        n = self.bm25.shape[0]
        extra_tokens = extra_tokens or []
        weights: dict[str, float] = {t: 1.0 for t in query_tokens}
        for t in extra_tokens:
            weights[t] = max(weights.get(t, 0.0), extra_weight)
        q1 = np.zeros(len(self.vocab), dtype=np.float32)
        for t, w in weights.items():
            j = self.vocab.get(t)
            if j is not None:
                q1[j] = w
        bm25 = np.asarray(self.bm25 @ q1).ravel() if q1.any() else np.zeros(n, dtype=np.float32)

        counts: dict[str, float] = {}
        for t in query_tokens + _bigrams(query_tokens):
            counts[t] = counts.get(t, 0.0) + 1.0
        for t in extra_tokens + _bigrams(extra_tokens):
            counts[t] = max(counts.get(t, 0.0), extra_weight)
        q2 = np.zeros(len(self.vocab2), dtype=np.float32)
        for t, c in counts.items():
            j = self.vocab2.get(t)
            if j is not None:
                q2[j] = (1 + math.log(max(c, 1.0))) * self.idf2[j] * min(c, 1.0)
        nq = float(np.linalg.norm(q2))
        tfidf = np.asarray(self.tfidf @ (q2 / nq)).ravel() if nq > 0 else np.zeros(n, dtype=np.float32)
        return bm25.astype(np.float32), tfidf.astype(np.float32)


# --------------------------------------------------------------------------- models (optional)
_embedder_fn = None  # injected in tests: fn(texts: list[str], is_query: bool) -> ndarray
_model = None
_model_error: str | None = None
_reranker = None
_reranker_error: str | None = None
_model_lock = threading.Lock()


def set_embedder(fn) -> None:
    global _embedder_fn
    _embedder_fn = fn


def _embed(texts: list[str], is_query: bool):
    """Return L2-normalised float32 embeddings, or None when no embedder is available."""
    global _model, _model_error
    try:
        if _embedder_fn is not None:
            arr = np.asarray(_embedder_fn(texts, is_query), dtype="float32")
        else:
            if _model_error is not None:
                return None
            with _model_lock:
                if _model is None:
                    from sentence_transformers import SentenceTransformer

                    _model = SentenceTransformer(EMBEDDING_MODEL)
            inputs = [BGE_QUERY_PREFIX + t for t in texts] if is_query and "bge" in EMBEDDING_MODEL.lower() else texts
            arr = np.asarray(
                _model.encode(inputs, batch_size=16, normalize_embeddings=True, convert_to_numpy=True,
                              show_progress_bar=False),
                dtype="float32",
            )
        norms = np.linalg.norm(arr, axis=1, keepdims=True)
        return arr / np.maximum(norms, 1e-9)
    except Exception as exc:
        _model_error = f"{type(exc).__name__}: {str(exc)[:160]}"
        log.warning("Dense embeddings unavailable (%s); continuing with sparse retrieval", _model_error)
        return None


def _rerank(query: str, texts: list[str]):
    global _reranker, _reranker_error
    if _reranker_error is not None:
        return None
    try:
        with _model_lock:
            if _reranker is None:
                from sentence_transformers import CrossEncoder

                _reranker = CrossEncoder(RERANKER_MODEL, max_length=512)
        return [float(s) for s in _reranker.predict([(query, t) for t in texts], show_progress_bar=False)]
    except Exception as exc:
        _reranker_error = f"{type(exc).__name__}: {str(exc)[:160]}"
        log.warning("Cross-encoder reranker unavailable (%s)", _reranker_error)
        return None


# --------------------------------------------------------------------------- index state
class Index:
    def __init__(self, rows: list[dict], dense=None, fingerprint: str = "", built_at: float | None = None):
        self.rows = rows
        self.texts = [_index_text(r) for r in rows]
        self.sparse = Sparse(self.texts)
        self.dense = dense
        self.fingerprint = fingerprint
        self.built_at = built_at or time.time()


_STATE: Index | None = None
_SEEN_MTIME: int | None = None
_LOCK = threading.RLock()
_INGEST_LOCK = threading.Lock()
_indexing = False
_last_error = ""


def _atomic_write(path: Path, writer) -> None:
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "wb") as fh:
        writer(fh)
    os.replace(tmp, path)


def _save_meta(idx: Index, skipped: list[dict]) -> None:
    global _SEEN_MTIME
    _atomic_write(INDEX / "metadata.json", lambda f: f.write(json.dumps(idx.rows).encode("utf-8")))
    manifest = {
        "version": INDEX_VERSION, "fingerprint": idx.fingerprint, "built_at": idx.built_at, "chunks": len(idx.rows),
        "sources": sorted({r["path"] for r in idx.rows}), "embedding_model": EMBEDDING_MODEL,
        "reranker_model": RERANKER_MODEL, "dense": idx.dense is not None, "chunk_size": CHUNK_SIZE,
        "chunk_overlap": CHUNK_OVERLAP, "skipped": skipped,
    }
    _atomic_write(INDEX / "manifest.json", lambda f: f.write(json.dumps(manifest, indent=2).encode("utf-8")))
    _SEEN_MTIME = (INDEX / "manifest.json").stat().st_mtime_ns


def _save_dense(idx: Index, skipped: list[dict]) -> None:
    _atomic_write(INDEX / "embeddings.npy", lambda f: np.save(f, idx.dense))
    try:  # FAISS copy is an optional persisted artefact; NumPy search is used when it is absent
        import faiss

        index = faiss.IndexFlatIP(idx.dense.shape[1])
        index.add(idx.dense)
        faiss.write_index(index, str(INDEX / "dense.faiss"))
    except Exception:
        pass
    _save_meta(idx, skipped)


def _load_from_disk() -> Index | None:
    global _SEEN_MTIME
    mp, fp, ep = INDEX / "metadata.json", INDEX / "manifest.json", INDEX / "embeddings.npy"
    if not (mp.exists() and fp.exists()):
        return None
    try:
        manifest = json.loads(fp.read_text("utf-8"))
        rows = json.loads(mp.read_text("utf-8"))
        mtime = fp.stat().st_mtime_ns
    except Exception:
        return None
    if manifest.get("version") != INDEX_VERSION or manifest.get("chunks") != len(rows) or not rows:
        return None
    dense = None
    if manifest.get("dense") and ep.exists() and manifest.get("embedding_model") == EMBEDDING_MODEL:
        try:
            arr = np.load(ep)
            if arr.ndim == 2 and arr.shape[0] == len(rows):
                dense = arr.astype("float32")
        except Exception:
            dense = None
    _SEEN_MTIME = mtime
    return Index(rows, dense, manifest.get("fingerprint", ""), manifest.get("built_at"))


def _disk_changed() -> bool:
    try:
        return (INDEX / "manifest.json").stat().st_mtime_ns != _SEEN_MTIME
    except OSError:
        return False


def _ensure() -> Index | None:
    global _STATE
    st = _STATE
    if st is not None and not _disk_changed():
        return st
    with _LOCK:
        if _STATE is not None and not _disk_changed():
            return _STATE
        loaded = _load_from_disk()
        if loaded is not None:
            _STATE = loaded
        return _STATE


def reset() -> None:
    """Forget in-memory state (used by tests and after manual corpus swaps)."""
    global _STATE, _SEEN_MTIME
    with _LOCK:
        _STATE, _SEEN_MTIME = None, None


def ingest_all(dense: bool = True) -> dict:
    """Rebuild the index. Phase 1 (sparse) publishes immediately; phase 2 adds dense vectors."""
    global _STATE, _indexing, _last_error
    started = time.perf_counter()
    with _INGEST_LOCK:
        _indexing = True
        try:
            rows, skipped = build_rows()
            if not rows:
                _STATE = None
                return {"chunks": 0, "sources": 0, "dense_embeddings": 0, "reranker": RERANKER_MODEL,
                        "skipped": skipped, "dense_ready": False}
            idx = Index(rows, None, corpus_fingerprint())
            _STATE = idx
            _save_meta(idx, skipped)
            if dense and not test_mode():
                emb = _embed(idx.texts, False)
                if emb is not None and emb.shape[0] == len(rows):
                    idx.dense = emb
                    _save_dense(idx, skipped)
                else:
                    _last_error = _model_error or "embedding unavailable"
            return {
                "chunks": len(rows), "sources": len({r["path"] for r in rows}),
                "dense_embeddings": len(rows) if idx.dense is not None else 0,
                "embedding_model": EMBEDDING_MODEL, "reranker": RERANKER_MODEL,
                "dense_ready": idx.dense is not None, "skipped": skipped,
                "seconds": round(time.perf_counter() - started, 2),
            }
        except Exception as exc:
            _last_error = f"{type(exc).__name__}: {exc}"[:300]
            raise
        finally:
            _indexing = False


def ensure_ready() -> dict:
    """Start-up warm-up: reuse a valid persisted index or rebuild; complete dense vectors if missing."""
    st = _ensure()
    if st is not None and st.fingerprint == corpus_fingerprint():
        if st.dense is None and not test_mode():
            with _INGEST_LOCK:
                emb = _embed(st.texts, False)
                if emb is not None and emb.shape[0] == len(st.rows):
                    st.dense = emb
                    _save_dense(st, [])
        return index_status()
    ingest_all()
    return index_status()


def chunk_counts() -> dict[str, int]:
    st = _ensure()
    out: dict[str, int] = {}
    for r in (st.rows if st else []):
        out[r["path"]] = out.get(r["path"], 0) + 1
    return out


# --------------------------------------------------------------------------- retrieval
def _norm(x: np.ndarray) -> np.ndarray:
    if len(x) == 0:
        return x
    mx, mn = float(x.max()), float(x.min())
    if mx - mn < 1e-9:
        return np.ones_like(x) if mx > 1e-9 else np.zeros_like(x)
    return (x - mn) / (mx - mn)


def _match(row: dict, filters: dict) -> bool:
    for key, value in filters.items():
        if value in (None, "", []):
            continue
        if key == "doc_type" and row.get("type") != value:
            return False
        if key == "source" and row.get("source") != value:
            return False
        if key == "path" and row.get("path") != value:
            return False
        if key == "section" and str(value).lower() not in row.get("section", "").lower():
            return False
    return True


def _mmr(rel: list[float], sim: np.ndarray, k: int, lam: float) -> list[int]:
    chosen: list[int] = []
    remaining = list(range(len(rel)))
    while remaining and len(chosen) < k:
        best, best_score = remaining[0], -1e9
        for i in remaining:
            redundancy = max((float(sim[i][j]) for j in chosen), default=0.0)
            score = lam * rel[i] - (1 - lam) * redundancy
            if score > best_score:
                best, best_score = i, score
        chosen.append(best)
        remaining.remove(best)
    return chosen


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, x))))


def search(query: str, k: int = 6, filters: dict | None = None, use_reranker: bool = True,
           topic_hint: str | None = None, diversify: bool = True) -> dict:
    """Hybrid search. Returns {'hits': [...], 'meta': {...}}."""
    t_start = time.perf_counter()
    st = _ensure()
    if st is None:
        ingest_all(dense=False)
        st = _ensure()
    meta = {"ready": st is not None, "mode": "none", "dense_used": False, "rerank_used": False,
            "expanded_terms": [], "candidates": 0, "coverage": 0.0, "confidence": 0.0, "abstain": True,
            "latency_ms": {}}
    if st is None or not query.strip():
        return {"hits": [], "meta": meta}

    filters = dict(filters or {})
    cand = np.array([i for i, r in enumerate(st.rows) if _match(r, filters)], dtype=int)
    meta["candidates"] = int(len(cand))
    if len(cand) == 0:
        meta["latency_ms"]["total"] = round((time.perf_counter() - t_start) * 1000, 2)
        return {"hits": [], "meta": meta}

    _, added = expand_query(query + (" " + topic_hint if topic_hint else ""))
    meta["expanded_terms"] = added
    t0 = time.perf_counter()
    bm25_all, tfidf_all = st.sparse.scores(tokenize(query), tokenize(" ".join(added) + (" " + topic_hint if topic_hint else "")))
    bm25, tfidf = bm25_all[cand], tfidf_all[cand]
    sparse_score = 0.6 * _norm(bm25) + 0.4 * _norm(tfidf)
    sparse_order = np.argsort(-sparse_score, kind="stable")[: min(TOP_SPARSE, len(cand))]
    meta["latency_ms"]["sparse"] = round((time.perf_counter() - t0) * 1000, 2)

    dense_score = np.zeros(len(cand), dtype=np.float32)
    dense_order = None
    if st.dense is not None and not test_mode():
        t0 = time.perf_counter()
        q = _embed([query], True)
        if q is not None and q.shape[1] == st.dense.shape[1]:
            dense_score = (st.dense[cand] @ q[0]).astype(np.float32)
            dense_order = np.argsort(-dense_score, kind="stable")[: min(TOP_DENSE, len(cand))]
            meta["dense_used"] = True
        meta["latency_ms"]["dense"] = round((time.perf_counter() - t0) * 1000, 2)

    fused: dict[int, float] = {}
    for rank, pos in enumerate(sparse_order, 1):
        if sparse_score[pos] > 0:
            fused[int(pos)] = fused.get(int(pos), 0.0) + 1.0 / (60 + rank)
    if dense_order is not None:
        for rank, pos in enumerate(dense_order, 1):
            fused[int(pos)] = fused.get(int(pos), 0.0) + 1.0 / (60 + rank)
    meta["mode"] = "hybrid" if meta["dense_used"] else "sparse"
    if not fused:
        meta["latency_ms"]["total"] = round((time.perf_counter() - t_start) * 1000, 2)
        return {"hits": [], "meta": meta}
    pool_pos = sorted(fused, key=fused.get, reverse=True)[: max(RERANK_K, k * 2)]

    rerank_scores = None
    if use_reranker and not test_mode() and meta["dense_used"]:
        t0 = time.perf_counter()
        rerank_scores = _rerank(query, [st.texts[int(cand[p])] for p in pool_pos])
        meta["latency_ms"]["rerank"] = round((time.perf_counter() - t0) * 1000, 2)
    meta["rerank_used"] = rerank_scores is not None

    if rerank_scores is not None:
        rel = [_sigmoid(s) for s in rerank_scores]
        order = sorted(range(len(pool_pos)), key=lambda i: -rerank_scores[i])
    else:
        dn = _norm(dense_score) if meta["dense_used"] else None
        rel = [float(0.5 * sparse_score[p] + 0.5 * dn[p]) if dn is not None else float(sparse_score[p]) for p in pool_pos]
        order = sorted(range(len(pool_pos)), key=lambda i: (-fused[pool_pos[i]], -rel[i]))

    if diversify and len(pool_pos) > 2:
        gidx = [int(cand[pool_pos[i]]) for i in order]
        xp = st.sparse.tfidf[gidx]
        sim = (xp @ xp.T).toarray()
        picked = [order[i] for i in _mmr([rel[i] for i in order], sim, k, MMR_LAMBDA)]
    else:
        picked = order[:k]

    hits = []
    for rank, i in enumerate(picked, 1):
        pos = pool_pos[i]
        row = dict(st.rows[int(cand[pos])])
        row.update({
            "rank": rank, "score": round(float(rel[i]), 4),
            "scores": {
                "bm25": round(float(bm25[pos]), 4), "tfidf": round(float(tfidf[pos]), 4),
                "dense": round(float(dense_score[pos]), 4) if meta["dense_used"] else None,
                "rrf": round(float(fused[pos]), 5),
                "rerank": round(float(rerank_scores[i]), 4) if rerank_scores is not None else None,
            },
        })
        hits.append(row)

    q_terms = salient_terms(query)
    covered: set[str] = set()
    for h in hits[:3]:
        covered |= set(tokenize(_index_text(h)))
    total_w = sum(st.sparse.term_idf(t) for t in q_terms)
    coverage = sum(st.sparse.term_idf(t) for t in q_terms & covered) / total_w if total_w > 0 else 0.0
    top_rel = rel[picked[0]] if picked else 0.0
    confidence = 0.5 * coverage + 0.5 * top_rel if rerank_scores is not None else coverage
    meta.update({
        "coverage": round(coverage, 3), "confidence": round(confidence, 3),
        "abstain": coverage < MIN_COVERAGE and (rerank_scores is None or top_rel < 0.3),
    })
    meta["latency_ms"]["total"] = round((time.perf_counter() - t_start) * 1000, 2)
    return {"hits": hits, "meta": meta}


def retrieve(query: str, k: int = 8, doc_type: str | None = None, filters: dict | None = None,
             use_reranker: bool = True) -> list[dict]:
    """Backwards-compatible helper returning only the hits."""
    f = dict(filters or {})
    if doc_type:
        f["doc_type"] = doc_type
    f.pop("topic", None)
    return search(query, k=k, filters=f, use_reranker=use_reranker)["hits"]


def index_status() -> dict:
    st = _ensure()
    has_faiss = False
    try:
        import faiss  # noqa: F401

        has_faiss = True
    except Exception:
        pass
    dense_ready = bool(st is not None and st.dense is not None)
    return {
        "ready": st is not None, "indexing": _indexing,
        "chunks": len(st.rows) if st else 0, "sources": len({r["path"] for r in st.rows}) if st else 0,
        "mode": "hybrid" if dense_ready and not test_mode() else "sparse",
        "dense_ready": dense_ready, "embedding_model": EMBEDDING_MODEL, "reranker_model": RERANKER_MODEL,
        "vector_store": "FAISS IndexFlatIP" if has_faiss else "NumPy exact inner product",
        "sparse_retrieval": "BM25 + TF-IDF (uni/bigram)", "hybrid": dense_ready,
        "embedding_error": _model_error, "reranker_error": _reranker_error, "last_error": _last_error or None,
        "fingerprint": (st.fingerprint[:12] if st else None), "built_at": st.built_at if st else None,
    }
