"""Citation and evidence checks. Pure Python so it can be unit-tested without any model or server."""
from __future__ import annotations

import re

from .textproc import salient_terms, sentences, tokenize

CITE_RE = re.compile(r"\[S(\d+)\]")
SUPPORT_THRESHOLD = 0.4


def strip_unknown_citations(answer: str, n_sources: int) -> str:
    """Remove [S#] markers that point to evidence that does not exist."""
    def repl(m: re.Match) -> str:
        return m.group(0) if 1 <= int(m.group(1)) <= n_sources else ""
    cleaned = re.sub(r"[ \t]{2,}", " ", CITE_RE.sub(repl, answer))
    return re.sub(r"[ \t]+([.,;!?])", r"\1", cleaned).strip()


def _terms(text: str) -> set[str]:
    return {t for t in tokenize(CITE_RE.sub(" ", text)) if len(t) >= 3}


def support_report(answer: str, evidence: list[dict]) -> dict:
    """Per-sentence support: which evidence chunk best explains each claim and how well."""
    ev_terms = [_terms(e.get("text", "") + " " + e.get("section", "")) for e in evidence]
    out = []
    for sent in sentences(answer):
        refs = [int(r) for r in CITE_RE.findall(sent)]
        words = _terms(sent)
        if len(words) < 2:  # headings, connectives, questions to the student
            out.append({"text": sent, "refs": refs, "support": None, "supported": None, "source": None, "cited": bool(refs)})
            continue
        pool = [r for r in refs if 1 <= r <= len(evidence)] or list(range(1, len(evidence) + 1))
        best, best_ref = 0.0, None
        for r in pool:
            frac = len(words & ev_terms[r - 1]) / len(words)
            if frac > best:
                best, best_ref = frac, r
        out.append({"text": sent, "refs": refs, "support": round(best, 3), "supported": best >= SUPPORT_THRESHOLD,
                    "source": best_ref, "cited": bool(refs)})
    claims = [s for s in out if s["supported"] is not None]
    return {
        "sentences": out,
        "support_score": round(sum(s["support"] for s in claims) / len(claims), 3) if claims else 0.0,
        "supported_ratio": round(sum(1 for s in claims if s["supported"]) / len(claims), 3) if claims else 0.0,
        "citation_ratio": round(sum(1 for s in claims if s["cited"]) / len(claims), 3) if claims else 0.0,
    }


def grounded_validate(answer: str, citations: list[dict], evidence: list[dict] | None = None) -> bool:
    """True when every citation exists and at least 75% of cited claims are supported by their evidence."""
    used = set(CITE_RE.findall(answer))
    ids = {str(c["id"])[1:] for c in citations}
    if not citations or not used or not used.issubset(ids):
        return False
    if not evidence:
        return True
    cited = [s for s in support_report(answer, evidence)["sentences"] if s["refs"] and s["supported"] is not None]
    if not cited:
        return True
    return sum(1 for s in cited if s["supported"]) / len(cited) >= 0.75


def extractive_answer(question: str, hits: list[dict], max_sentences: int = 5) -> tuple[str, list[int]]:
    """Deterministic, citation-bearing answer assembled from the best-matching evidence sentences.

    Used when no language model is reachable so the tutor still produces something useful and verifiable."""
    q_terms = salient_terms(question)
    seen: set[str] = set()
    scored = []
    for rank, h in enumerate(hits[:4], 1):
        for pos, sent in enumerate(sentences(h["text"])):
            key = re.sub(r"\W+", " ", sent.lower()).strip()
            if len(key) < 25 or key in seen:
                continue
            seen.add(key)
            overlap = len(q_terms & set(tokenize(sent))) / max(1, len(q_terms))
            scored.append((overlap + 0.3 / rank, rank, pos, sent))
    scored.sort(key=lambda x: -x[0])
    chosen = sorted(scored[:max_sentences], key=lambda x: (x[1], x[2]))
    if not chosen:
        return "", []
    lines = [f"- {sent.rstrip()} [S{rank}]" for _, rank, _, sent in chosen]
    used = sorted({c[1] for c in chosen})
    return "From the course notes:\n\n" + "\n".join(lines), used
