"""Answer- and retrieval-quality metrics. Pure Python (no model required)."""
from __future__ import annotations

import math
import re

from .textproc import tokenize

_CITE = re.compile(r"\[S(\d+)\]")


def _content_terms(text: str) -> set[str]:
    return {t for t in tokenize(_CITE.sub(" ", text)) if len(t) >= 4}


def metrics(answer: str, sources: list[dict], gold_concepts: list[str]) -> dict:
    ids = set(_CITE.findall(answer))
    valid = {str(i + 1) for i in range(len(sources))}
    citation_precision = len(ids & valid) / len(ids) if ids else 0.0
    answer_terms = _content_terms(answer)
    source_terms = _content_terms(" ".join(s["text"] for s in sources))
    grounded = len(answer_terms & source_terms) / len(answer_terms) if answer_terms else 0.0
    low = answer.lower()
    coverage = sum(c.lower() in low for c in gold_concepts) / len(gold_concepts) if gold_concepts else 0.0
    return {
        "citation_correctness": round(citation_precision, 3),
        "groundedness": round(grounded, 3),
        "hallucination_rate_proxy": round(max(0.0, 1 - grounded), 3),
        "concept_coverage": round(coverage, 3),
        "answer_relevance": round(coverage, 3),
    }


def retrieval_metrics(hits: list[dict], gold_sources: list[str], k: int = 5) -> dict:
    """Recall@k and nDCG@k are computed on distinct sources; MRR on the first relevant chunk."""
    gold = set(gold_sources)
    chunks = [h.get("source") for h in hits[:k]]
    ranked: list[str] = []
    for s in chunks:
        if s not in ranked:
            ranked.append(s)
    recall = len(set(ranked) & gold) / max(1, len(gold))
    rr = next((1 / i for i, s in enumerate(chunks, 1) if s in gold), 0.0)
    dcg = sum(1 / math.log2(i + 2) for i, s in enumerate(ranked) if s in gold)
    ideal = sum(1 / math.log2(i + 2) for i in range(min(len(gold), k)))
    return {
        "recall_at_k": round(recall, 3),
        "mrr": round(rr, 3),
        "ndcg_at_k": round(dcg / ideal if ideal else 0.0, 3),
        "hit_at_1": 1.0 if chunks and chunks[0] in gold else 0.0,
    }


def aggregate(rows: list[dict], keys: list[str]) -> dict:
    return {k: round(sum(r[k] for r in rows) / len(rows), 3) if rows else 0.0 for k in keys}


def evaluate_retrieval(benchmark: list[dict], search_fn, k: int = 5) -> dict:
    """Run retrieval-only evaluation. search_fn(question, k) -> {'hits': [...], 'meta': {...}}."""
    cases, oos = [], []
    for item in benchmark:
        res = search_fn(item["question"], k)
        if item.get("out_of_scope"):
            oos.append({"id": item["id"], "query": item["question"], "abstained": bool(res["meta"].get("abstain"))})
            continue
        row = {"id": item["id"], "query": item["question"], "difficulty": item.get("difficulty"),
               **retrieval_metrics(res["hits"], item.get("gold_sources", []), k),
               "top_source": res["hits"][0]["source"] if res["hits"] else None,
               "abstained": bool(res["meta"].get("abstain"))}
        cases.append(row)
    agg = aggregate(cases, ["recall_at_k", "mrr", "ndcg_at_k", "hit_at_1"])
    agg["false_abstain_rate"] = round(sum(c["abstained"] for c in cases) / len(cases), 3) if cases else 0.0
    agg["abstention_accuracy"] = round(sum(o["abstained"] for o in oos) / len(oos), 3) if oos else None
    return {"k": k, "benchmark_size": len(cases), "out_of_scope": len(oos), "aggregate": agg, "cases": cases, "oos_cases": oos}
