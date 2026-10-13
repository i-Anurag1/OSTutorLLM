#!/usr/bin/env python3
"""Compare models (base vs fine-tuned) on the held-out test split, with metrics that need no judge model.

    python training/evaluate_models.py --models qwen3:8b ostutor-qwen3 --limit 80
    python training/evaluate_models.py --selftest        # validates the scoring code with references and degenerate baselines
Metrics: valid-citation rate, citation rate on grounded answers, groundedness (evidence support), abstention accuracy,
exact-match on computed worked problems and quiz answers.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.request
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("OSTUTOR_DATA_DIR", str(ROOT / "backend" / "data"))

from app.grounding import CITE_RE, support_report  # noqa: E402

ABSTAIN = re.compile(r"could not find|can't answer|cannot answer|does not (?:include|contain|cover)|not covered|will not guess|insufficient", re.I)


def evidence_of(rec: dict) -> list[dict]:
    user = rec["messages"][-2]["content"] if rec["messages"][-1]["role"] == "assistant" else rec["messages"][-1]["content"]
    blocks = re.findall(r"^\[S(\d+)\] \(([^\n]*)\)\n(.*?)(?=\n\n\[S\d+\] \(|\n\nQUESTION)", user, re.S | re.M)
    return [{"text": t, "section": s} for _, s, t in blocks]


def final_answer(text: str) -> str:
    m = re.findall(r"Final answer:\s*(.+)", text)
    return re.sub(r"[*`\s]+$", "", m[-1].strip()).lower() if m else ""


def score_output(rec: dict, output: str) -> dict:
    meta, ev = rec["meta"], evidence_of(rec)
    used = [int(x) for x in CITE_RE.findall(output)]
    res = {"valid_citations": all(1 <= u <= len(ev) for u in used), "cited": bool(used)}
    if meta.get("abstain"):
        res["abstained"] = bool(ABSTAIN.search(output)) and not used
    elif rec["type"].startswith("worked"):
        res["exact"] = final_answer(output) == str(meta["reference"]).lower()
    elif rec["type"] == "quiz_explain":
        m = re.search(r"correct answer is \W*([A-D])\)", output)
        res["exact"] = bool(m) and m.group(1) == meta["reference"]
    elif ev:
        res["support"] = support_report(CITE_RE.sub("", output), ev)["support_score"]
    return res


def summarise(scored: list[tuple[dict, dict]]) -> dict:
    groups = defaultdict(list)
    for rec, s in scored:
        kind = "abstain" if rec["meta"].get("abstain") else ("worked" if rec["type"].startswith("worked") else ("quiz" if rec["type"] == "quiz_explain" else "grounded"))
        groups[kind].append(s)
    rate = lambda xs, k: round(sum(1 for x in xs if x.get(k)) / len(xs), 3) if xs else None  # noqa: E731
    allv = [s for _, s in scored]
    return {"examples": len(scored), "valid_citation_rate": rate(allv, "valid_citations"),
            "grounded_cited_rate": rate(groups["grounded"], "cited"),
            "grounded_support": round(sum(x["support"] for x in groups["grounded"]) / len(groups["grounded"]), 3) if groups["grounded"] else None,
            "abstention_accuracy": rate(groups["abstain"], "abstained"), "worked_exact_match": rate(groups["worked"], "exact"),
            "quiz_exact_match": rate(groups["quiz"], "exact"), "n_by_group": {k: len(v) for k, v in groups.items()}}


def ollama_chat(url: str, model: str, messages: list[dict]) -> str:
    body = json.dumps({"model": model, "messages": messages, "stream": False, "think": False,
                       "options": {"temperature": 0, "num_predict": 700, "num_ctx": 4096}}).encode()
    req = urllib.request.Request(url.rstrip("/") + "/api/chat", body, {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.loads(r.read())["message"]["content"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="*", default=[])
    ap.add_argument("--split", default="test")
    ap.add_argument("--limit", type=int, default=80)
    ap.add_argument("--url", default="http://localhost:11434")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--out", default=str(ROOT / "training" / "outputs" / "model_comparison.json"))
    args = ap.parse_args()
    recs = [json.loads(l) for l in (ROOT / "training" / "data" / "processed" / f"{args.split}.jsonl").read_text("utf-8").splitlines() if l.strip()]
    recs = recs[: args.limit]
    results = {}
    if args.selftest:
        results["reference_answers (upper bound)"] = summarise([(r, score_output(r, r["messages"][-1]["content"])) for r in recs])
        results["empty_output"] = summarise([(r, score_output(r, "")) for r in recs])
        results["hallucinating_baseline"] = summarise([(r, score_output(r, "Operating systems are great [S9].")) for r in recs])
    for model in args.models:
        outs = []
        for i, r in enumerate(recs):
            outs.append((r, score_output(r, ollama_chat(args.url, model, r["messages"][:-1]))))
            print(f"\r{model}: {i + 1}/{len(recs)}", end="", flush=True)
        print()
        results[model] = summarise(outs)
    print(json.dumps(results, indent=2))
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(results, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
