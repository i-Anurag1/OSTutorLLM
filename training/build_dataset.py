#!/usr/bin/env python3
"""Build the ORIGINAL OSTutor fine-tuning dataset and run the preprocessing pipeline.

Provenance (nothing is scraped or copied from third parties):
  corpus     - sections of backend/data/documents, written for this project, restructured into tutor answers
  worked     - randomly generated numeric problems whose answers are computed by backend/app/simulators.py
  quiz       - explanations from backend/data/question_bank.json (authored for this project)
  abstain    - original off-topic and near-miss questions paired with real (irrelevant) retrieval results
Prompts are produced by the application's own prompt builder and retrieval, so training matches serving.

Preprocessing stages (counts for each are written to data/processed/preprocessing_report.json):
  1 unicode/whitespace normalisation   2 PII and link scrub        3 length and language filters
  4 citation-integrity check           5 groundedness check        6 exact de-duplication
  7 near-duplicate removal (Jaccard)   8 benchmark decontamination 9 leakage-safe grouped split + stats

Usage:  python training/build_dataset.py            (offline, deterministic)
        python training/build_dataset.py --teacher http://localhost:11434 --teacher-model qwen3:14b
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import shutil
import sys
import tempfile
import unicodedata
import urllib.request
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
_TMP = tempfile.mkdtemp(prefix="ostutor-ds-")  # retrieval runs on a throw-away copy; nothing is written to the repo
shutil.copytree(ROOT / "backend" / "data" / "documents", Path(_TMP) / "documents")
os.environ["OSTUTOR_DATA_DIR"] = _TMP
os.environ["OSTUTOR_TEST_MODE"] = "1"

from app import rag, simulators as sim  # noqa: E402
from app.grounding import CITE_RE, support_report  # noqa: E402
from app.textproc import sentences, tokenize  # noqa: E402
from app.tutor import abstain_message, build_messages  # noqa: E402

OUT = ROOT / "training" / "data" / "processed"
SEED = 20261010
SMART = str.maketrans({"\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"', "\u2013": "-", "\u2014": "-", "\u00a0": " "})

OFF_TOPIC = [
    "Who won the football world cup in 2018?", "What is the capital of Australia?", "Give me a recipe for banana bread.",
    "How do I center a div in CSS?", "What is the derivative of x squared?", "Who painted the Mona Lisa?",
    "Explain how vaccines work.", "What is the best way to learn guitar?", "How tall is Mount Everest?",
    "Write a poem about autumn.", "What is the stock price of Apple today?", "How do airplanes stay in the air?",
    "What are the symptoms of the flu?", "Translate 'good morning' into French.", "Who is the current prime minister of Canada?",
    "What is the plot of Hamlet?", "How do I train for a marathon?", "Explain the theory of relativity.",
    "What is the boiling point of water on Mars?", "Which programming language should I learn for web design?",
    "How does a blockchain work?", "What is photosynthesis?", "Recommend a good science fiction novel.",
    "How do I tie a tie?", "What causes inflation in an economy?", "How many calories are in an avocado?",
    "What is the tallest building in the world?", "How do I write a cover letter?", "Explain quantum entanglement.",
    "Who invented the telephone?",
]
NEAR_MISS = [  # (concept the notes do not cover, corpus file with the closest material)
    ("the Linux Completely Fair Scheduler and vruntime", "02_process_scheduling.md"), ("the ZFS file system and its checksums", "09_file_systems.md"),
    ("the NTFS master file table", "09_file_systems.md"), ("the Windows registry", "01_foundations.md"),
    ("the RISC-V privileged architecture", "01_foundations.md"), ("io_uring submission queues", "15_io_storage.md"),
    ("Kubernetes pod scheduling", "02_process_scheduling.md"), ("the Rust borrow checker", "04_synchronization.md"),
    ("CUDA unified memory", "13_virtual_memory.md"), ("NUMA balancing in Linux", "06_memory_management.md"),
    ("the seL4 microkernel proof", "01_foundations.md"), ("eBPF programs", "12_system_calls.md"),
    ("systemd unit file syntax", "01_foundations.md"), ("Docker overlay filesystems", "09_file_systems.md"),
    ("transactional memory", "04_synchronization.md"), ("the Linux OOM score algorithm", "13_virtual_memory.md"),
]
TEACH_Q = ["Explain {x}.", "What is {x}?", "Can you walk me through {x}?", "I'm revising for my OS exam. Help me understand {x}.",
           "Give me a quick explanation of {x} in operating systems."]
EXAM_Q = ["Exam question: write a short note on {x}.", "In exam style, summarise {x}.", "Briefly answer for an exam: {x}."]
SOCRATIC_Q = ["Help me figure out {x} without just telling me the answer.", "Guide me through {x}.", "Quiz me gently on {x}."]
GUIDE = ["What problem does {x} solve, and what would go wrong without it?", "Can you think of a situation where {x} behaves badly?",
         "How would you explain {x} to a classmate using a small example?", "Which other idea from this course is {x} most closely related to, and why?"]


# ----------------------------------------------------------------------------- helpers
def topic_phrase(section: str) -> str:
    s = re.sub(r"\s*\([^)]*\)", "", section).strip()
    return s[0].lower() + s[1:] if s[:2] != s[:2].upper() else s


def make_example(kind, mode, question, hits, answer, source, group, **meta):
    return {"type": kind, "mode": mode, "source": source, "group": group, "question": question, "hits": hits, "answer": answer, "meta": meta}


def evidence(rows_pos: list[dict], pool: list[dict], rng: random.Random, n_distract: int) -> list[dict]:
    paths = {r["path"] for r in rows_pos}
    others = [r for r in pool if r["path"] not in paths]
    chosen = list(rows_pos) + rng.sample(others, min(n_distract, len(others)))
    rng.shuffle(chosen)
    return chosen


def idx(hits: list[dict], row: dict) -> int:
    return next(i for i, h in enumerate(hits, 1) if h["id"] == row["id"])


# ----------------------------------------------------------------------------- generators
def gen_corpus(rows, rng):
    out = []
    for row in rows:
        sents = [s for s in sentences(row["text"]) if len(s) > 20]
        if len(sents) < 2:
            continue
        x = topic_phrase(row["section"])
        for variant in range(2):
            hits = evidence([row], rows, rng, rng.choice([0, 1, 2]))
            ref = idx(hits, row)
            q = rng.choice(TEACH_Q).format(x=x)
            bullets = "\n".join(f"- {s} [S{ref}]" for s in sents[1:7])
            out.append(make_example("corpus_teach", "teach", q, hits, f"**{row['section']}**\n\n{sents[0]} [S{ref}]\n\n{bullets}", row["source"], row["id"], cited=[ref]))
            if variant == 0:
                hits = evidence([row], rows, rng, rng.choice([0, 1]))
                ref = idx(hits, row)
                pts = "\n".join(f"- {s} [S{ref}]" for s in sents[1:4])
                out.append(make_example("corpus_exam", "exam", rng.choice(EXAM_Q).format(x=x), hits, f"{sents[0]} [S{ref}]\n\n{pts}", row["source"], row["id"], cited=[ref]))
                hits = evidence([row], rows, rng, rng.choice([0, 1]))
                ref = idx(hits, row)
                qs = rng.sample(GUIDE, 2)
                guide = "\n".join(f"{n}. {g.format(x=x)}" for n, g in enumerate(qs, 1))
                out.append(make_example("corpus_socratic", "socratic", rng.choice(SOCRATIC_Q).format(x=x), hits,
                                        f"Here is a hint to start from: {sents[0]} [S{ref}]\n\nNow try these:\n{guide}", row["source"], row["id"], cited=[ref]))
        for s_i, s in enumerate(sents[:4]):  # definition mining: "A deadlock is ..." -> "What is a deadlock?"
            m = re.match(r"^(An?|The)\s+([A-Za-z'()\- ]{3,48}?)\s+(is|are)\s+\S", s)
            if m and "," not in m.group(2) and s_i < len(sents):
                hits = evidence([row], rows, rng, 1)
                ref = idx(hits, row)
                nxt = f" {sents[s_i + 1]} [S{ref}]" if s_i + 1 < len(sents) else ""
                out.append(make_example("corpus_define", "teach", f"What {m.group(3)} {m.group(1).lower()} {m.group(2)}?", hits, f"{s} [S{ref}]{nxt}", row["source"], row["id"], cited=[ref]))
                break
    return out


def pick(rows, fname, key=""):
    cand = [r for r in rows if r["source"] == fname and key.lower() in r["section"].lower()]
    return cand[0] if cand else None


def finish(kind, mode, q, rows, rng, fname, key, lead, body, ref, group):
    row = pick(rows, fname, key)
    hits = evidence([row], rows, rng, rng.choice([0, 1]))
    n = idx(hits, row)
    answer = f"{lead.replace('{n}', str(n))}\n\n{body}\n\nFinal answer: {ref}"
    return make_example(kind, mode, q, hits, answer, fname, group, cited=[n], reference=ref)


def gen_worked(rows, rng, n_each=45):
    out = []
    for i in range(n_each):  # CPU scheduling
        alg = rng.choice(["FCFS", "SJF", "Round Robin", "SRTF", "Priority"])
        procs = [{"pid": f"P{k + 1}", "arrival": rng.randint(0, 5) if (alg == "SRTF" or rng.random() < 0.5) else 0,
                  "burst": rng.randint(2, 10), "priority": rng.randint(1, 4)} for k in range(rng.randint(3, 5))]
        quantum = rng.randint(2, 4)
        r = sim.cpu_scheduling(alg, procs, quantum)
        desc = "; ".join(f"{p['pid']} (arrival {p['arrival']}, burst {p['burst']}" + (f", priority {p['priority']}" if alg == "Priority" else "") + ")" for p in procs)
        extra = f" with time quantum {quantum}" if alg == "Round Robin" else (" (a smaller number means higher priority)" if alg == "Priority" else "")
        q = f"Processes: {desc}. Using {alg}{extra}, what is the average waiting time? Show the schedule."
        gantt = " | ".join(f"{s['pid']} {s['start']}-{s['end']}" for s in r["timeline"])
        lines = "\n".join(f"- {m['pid']}: completion {m['completion']}, turnaround {m['completion']} - {m['arrival']} = {m['turnaround']}, waiting {m['turnaround']} - {m['burst']} = {m['waiting']}" for m in r["metrics"])
        total = " + ".join(str(m["waiting"]) for m in r["metrics"])
        ref = f"{r['avg_waiting']:.2f}"
        key = {"FCFS": "First-Come", "SJF": "Shortest Job", "SRTF": "Shortest Job", "Round Robin": "Round Robin", "Priority": "Priority"}[alg]
        out.append(finish("worked_cpu", "teach", q, rows, rng, "02_process_scheduling.md", key,
                          "Turnaround time is completion minus arrival, and waiting time is turnaround minus burst [S{n}].",
                          f"Schedule ({alg}): {gantt}\n\n{lines}\n\nAverage waiting time = ({total}) / {len(procs)} = {ref}.", ref, f"cpu-{i}"))
    for i in range(n_each):  # page replacement
        alg = rng.choice(["FIFO", "LRU", "Optimal"])
        refs = [rng.randint(0, 6) for _ in range(rng.randint(12, 15))]
        f = rng.choice([3, 4])
        r = sim.page_replacement(alg, refs, f)
        q = f"Reference string {', '.join(map(str, refs))} with {f} frames. How many page faults does {alg} cause?"
        steps = "\n".join(f"- {s['reference']}: {'hit' if s['hit'] else 'fault' + (f', evict {s['victim']}' if s['victim'] is not None else '')} -> [{', '.join('-' if x is None else str(x) for x in s['frames'])}]" for s in r["steps"])
        ref = str(r["faults"])
        key = {"FIFO": "FIFO page", "LRU": "LRU page", "Optimal": "Optimal page"}[alg]
        out.append(finish("worked_page", "teach", q, rows, rng, "07_page_replacement.md", key,
                          {"FIFO": "FIFO evicts the page that has been in memory the longest [S{n}].", "LRU": "LRU evicts the page that has not been used for the longest time [S{n}].",
                           "Optimal": "Optimal evicts the page that will not be used for the longest time in the future [S{n}]."}[alg],
                          f"Tracing {alg} with {f} frames:\n{steps}\n\nTotal: {r['faults']} page faults and {r['hits']} hits.", ref, f"page-{i}"))
    for i in range(n_each):  # disk scheduling
        alg = rng.choice(sim.DISK_ALGORITHMS)
        reqs = rng.sample(range(0, 200), rng.randint(6, 8))
        head = rng.randint(0, 199)
        d = rng.choice(["up", "down"]) if alg not in ("FCFS", "SSTF") else "up"
        r = sim.disk_scheduling(alg, reqs, head, 200, d)
        dirn = f", initially moving toward {'higher' if d == 'up' else 'lower'} cylinders" if alg not in ("FCFS", "SSTF") else ""
        q = f"Disk with cylinders 0-199, head at {head}, queue {', '.join(map(str, reqs))}{dirn}. Find the total head movement under {alg}."
        moves = "\n".join(f"- {s['from']} -> {s['to']} = {s['distance']}" for s in r["segments"])
        ref = str(r["movement"])
        key = {"FCFS": "FCFS and SSTF", "SSTF": "FCFS and SSTF", "SCAN": "SCAN (elevator)", "C-SCAN": "C-SCAN", "LOOK": "LOOK and C-LOOK", "C-LOOK": "LOOK and C-LOOK"}[alg]
        out.append(finish("worked_disk", "teach", q, rows, rng, "10_disk_scheduling.md", key,
                          f"{alg} serves requests in the order {', '.join(map(str, r['order']))} [S{{n}}].",
                          f"Head movements:\n{moves}\n\nTotal head movement = {ref} cylinders (return jumps are counted).", ref, f"disk-{i}"))
    for i in range(n_each):  # paging address translation
        size = rng.choice([64, 128, 256, 512, 1024])
        table = dict(zip(range(6), rng.sample(range(0, 12), 6)))
        page = rng.randint(0, 5)
        off = rng.randint(0, size - 1)
        addr = page * size + off
        frame = table[page]
        phys = frame * size + off
        q = f"Page size is {size} bytes and the page table maps pages to frames as {table}. Translate logical address {addr}."
        ref = str(phys)
        out.append(finish("worked_paging", "teach", q, rows, rng, "06_memory_management.md", "Paging",
                          "The page number is the address divided by the page size, the offset is the remainder, and the physical address is frame times page size plus offset [S{n}].",
                          f"- Page number = {addr} div {size} = {page}\n- Offset = {addr} mod {size} = {off}\n- Page {page} is in frame {frame}\n- Physical address = {frame} * {size} + {off} = {phys}", ref, f"paging-{i}"))
    for i in range(n_each):  # effective access time
        h, t, m = rng.choice([0.7, 0.75, 0.8, 0.85, 0.9, 0.95, 0.98]), rng.choice([10, 20, 30]), rng.choice([80, 100, 120])
        eat = h * (t + m) + (1 - h) * (t + 2 * m)
        q = f"TLB hit ratio {h}, TLB lookup {t} ns, memory access {m} ns. What is the effective access time?"
        ref = f"{eat:.2f} ns"
        out.append(finish("worked_eat", "teach", q, rows, rng, "06_memory_management.md", "Page table and TLB",
                          "With hit ratio h, TLB time t and memory time m, EAT = h * (t + m) + (1 - h) * (t + 2m) [S{n}].",
                          f"EAT = {h} * ({t} + {m}) + {round(1 - h, 2)} * ({t} + 2 * {m}) = {h * (t + m):.2f} + {(1 - h) * (t + 2 * m):.2f} = {eat:.2f} ns.", ref, f"eat-{i}"))
    for i in range(n_each):  # Banker's algorithm
        n, m = rng.randint(3, 4), 3
        alloc = [[rng.randint(0, 3) for _ in range(m)] for _ in range(n)]
        mx = [[a + rng.randint(0, 4) for a in row] for row in alloc]
        avail = [rng.randint(0, 4) for _ in range(m)]
        r = sim.bankers(alloc, mx, avail)
        q = f"Banker's algorithm. Allocation {alloc}, Max {mx}, Available {avail}. Is the state safe? Give a safe sequence if one exists."
        need = "\n".join(f"- P{k}: {r['need'][k]}" for k in range(n))
        trace = "\n".join(f"- P{s['process']} can finish because Need {s['need']} <= Work {s['work_before']}; Work becomes {s['work_after']}" for s in r["steps"])
        ref = "safe " + str(r["sequence"]) if r["safe"] else "unsafe"
        tail = "Safe sequence: " + ", ".join(f"P{k}" for k in r["sequence"]) + "." if r["safe"] else "No remaining process has a Need that fits in Work, so the state is unsafe."
        out.append(finish("worked_banker", "teach", q, rows, rng, "05_deadlocks.md", "Banker's algorithm",
                          "Need = Max - Allocation, and the safety algorithm repeatedly finds a process whose Need fits in Work [S{n}].",
                          f"Need matrix:\n{need}\n\nSafety check starting from Work = {avail}:\n{trace or '- no process can finish'}\n\n{tail}", ref, f"banker-{i}"))
    for i in range(n_each):  # segmentation
        segs = [{"base": rng.randrange(100, 9000, 100), "limit": rng.randrange(50, 600, 50)} for _ in range(rng.randint(3, 4))]
        s_i = rng.randint(0, len(segs) - 1)
        off = rng.randint(0, segs[s_i]["limit"] + 150)
        r = sim.segmentation(segs, [{"segment": s_i, "offset": off}])["rows"][0]
        table = "; ".join(f"segment {k}: base {s['base']}, limit {s['limit']}" for k, s in enumerate(segs))
        q = f"Segment table: {table}. Translate logical address (segment {s_i}, offset {off})."
        ref = str(r["physical"]) if r["valid"] else "trap"
        body = (f"- Segment {s_i} has base {r['base']} and limit {r['limit']}\n- The offset {off} is " + (f"below the limit, so physical address = {r['base']} + {off} = {r['physical']}." if r["valid"] else f"not below the limit {r['limit']}, so the hardware traps with a segmentation fault."))
        out.append(finish("worked_seg", "teach", q, rows, rng, "08_segmentation.md", "Segment table",
                          "An address is valid only if its offset is less than the segment limit, and then physical = base + offset [S{n}].", body, ref, f"seg-{i}"))
    return out


def gen_abstain(rows, rng):
    out = []
    for q in OFF_TOPIC:
        for _ in range(2):
            res = rag.search(q, k=3)["hits"] or rng.sample(rows, 2)
            out.append(make_example("abstain_offtopic", "teach", q, res, abstain_message(q), "none", "oos-" + q, abstain=True))
    for concept, fname in NEAR_MISS:
        near = [r for r in rows if r["source"] == fname]
        for tmpl in ("Explain {c}.", "How does {c} work?"):
            q = tmpl.format(c=concept)
            hits = rng.sample(near, min(2, len(near))) + rng.sample([r for r in rows if r["source"] != fname], 1)
            rng.shuffle(hits)
            secs = [h["section"] for h in hits if h["source"] == fname][:2]
            ans = (f"The course material I have covers {' and '.join(secs)}, but it does not include {concept}, so I can't answer that reliably from these sources. "
                   f"If you tell me which part of {secs[0]} you are curious about, I can explain it.")
            out.append(make_example("abstain_nearmiss", "teach", q, hits, ans, fname, f"nm-{concept}-{tmpl}", abstain=True))
    return out


def gen_quiz(rows, rng):
    out = []
    for qd in json.loads((ROOT / "backend" / "data" / "question_bank.json").read_text("utf-8")):
        if qd["kind"] != "mcq":
            continue
        letters = "ABCD"
        q = f"Question: {qd['prompt']}\n" + "\n".join(f"{letters[i]}) {o}" for i, o in enumerate(qd["options"])) + "\n\nWhich option is correct, and why?"
        hits = rag.search(qd["prompt"], k=3)["hits"]
        correct = qd["options"][letters.index(qd["answer"])]
        base = f"The correct answer is **{qd['answer']}) {correct}**. {qd['explanation']}"
        ref = next((i for i, h in enumerate(hits, 1) if support_report(base, [h])["support_score"] >= 0.4), None)
        out.append(make_example("quiz_explain", "teach", q, hits, base + (f" [S{ref}]" if ref else ""), "question_bank", "quiz-" + qd["prompt"],
                                cited=[ref] if ref else [], reference=qd["answer"]))
    return out


def teacher_answers(examples, url, model, rng, limit=400):
    """Optional: let a local LLM write the answers (rejection-sampled by preprocessing stages 4 and 5)."""
    done = 0
    for ex in examples:
        if ex["type"] not in ("corpus_teach", "corpus_define") or done >= limit:
            continue
        msgs = build_messages(ex["question"], ex["hits"], ex["mode"], "medium", None, 50)
        body = json.dumps({"model": model, "messages": msgs, "stream": False, "think": False, "options": {"temperature": 0.3}}).encode()
        try:
            req = urllib.request.Request(url.rstrip("/") + "/api/chat", body, {"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=300) as r:
                ex["answer"] = json.loads(r.read())["message"]["content"].strip()
                ex["type"] += "_teacher"
                done += 1
        except Exception as exc:  # keep the template answer if the teacher is unavailable
            print("teacher unavailable:", exc)
            break
    return done


# ----------------------------------------------------------------------------- preprocessing
def normalize(t: str) -> str:
    t = unicodedata.normalize("NFKC", t).translate(SMART)
    t = re.sub(r"[\u0000-\u0008\u000b\u000c\u000e-\u001f\u200b-\u200d\ufeff]", "", t)
    t = re.sub(r"[ \t]+\n", "\n", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return re.sub(r"[ \t]{2,}", " ", t).strip()


def scrub(t: str) -> tuple[str, int]:
    n = 0
    for pat, repl in ((r"[\w.+-]+@[\w-]+\.[\w.-]+", "[email]"), (r"https?://\S*[^\s.,;:!?)]", "[link]"), (r"\b\d{10,}\b", "[number]")):
        t, c = re.subn(pat, repl, t)
        n += c
    return t, n


def shingles(t: str, n: int = 3) -> set:
    toks = tokenize(t, drop_stop=False, do_stem=False)
    return {" ".join(toks[i:i + n]) for i in range(max(1, len(toks) - n + 1))}


def jaccard(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if a and b else 0.0


def preprocess(examples: list[dict], benchmark: list[dict]) -> tuple[list[dict], dict]:
    rep = {"stages": []}

    def log(name, before, after, **extra):
        rep["stages"].append({"stage": name, "before": before, "after": after, "removed": before - after, **extra})

    n0 = len(examples)
    scrubbed = 0
    for ex in examples:
        ex["question"] = normalize(ex["question"])
        ex["answer"] = normalize(ex["answer"])
        for h in ex["hits"]:
            h["text"] = normalize(h["text"])
        ex["question"], a = scrub(ex["question"])
        ex["answer"], b = scrub(ex["answer"])
        scrubbed += a + b
    log("1 normalise unicode and whitespace", n0, len(examples))
    log("2 scrub PII, links and long numbers", len(examples), len(examples), replacements=scrubbed)

    keep = [e for e in examples if 15 <= len(e["answer"]) <= 3500 and 8 <= len(e["question"]) <= 900
            and sum(c.isascii() for c in e["answer"]) / len(e["answer"]) > 0.97]
    log("3 length and language (ASCII ratio) filters", len(examples), len(keep))
    examples = keep

    def citations_ok(e):
        used = [int(x) for x in CITE_RE.findall(e["answer"])]
        if e["meta"].get("abstain"):
            return not used
        return all(1 <= u <= len(e["hits"]) for u in used) and (bool(used) or e["type"] == "quiz_explain")
    keep = [e for e in examples if citations_ok(e)]
    log("4 citation integrity (ids exist, abstentions uncited)", len(examples), len(keep))
    examples = keep

    def grounded(e):
        if e["meta"].get("abstain") or e["type"].startswith("worked") or e["type"] == "quiz_explain" or e["type"].startswith("corpus_socratic"):
            return True
        return support_report(CITE_RE.sub("", e["answer"]), [e["hits"][i - 1] for i in e["meta"]["cited"]])["support_score"] >= 0.5
    keep = [e for e in examples if grounded(e)]
    log("5 groundedness (answer supported by cited evidence)", len(examples), len(keep))
    examples = keep

    seen, keep = set(), []
    for e in examples:
        h = hashlib.sha256((e["question"] + "||" + e["answer"] + "||" + "".join(x["id"] for x in e["hits"])).lower().encode()).hexdigest()
        if h not in seen:
            seen.add(h)
            keep.append(e)
    log("6 exact de-duplication", len(examples), len(keep))
    examples = keep

    keep, sigs = [], []
    for e in examples:
        s = shingles(e["question"] + " " + e["answer"])
        if any(jaccard(s, o) >= 0.9 for o in sigs[-400:]):
            continue
        sigs.append(s)
        keep.append(e)
    log("7 near-duplicate removal (3-gram Jaccard >= 0.9)", len(examples), len(keep))
    examples = keep

    bench = [set(tokenize(b["question"])) for b in benchmark]
    keep = [e for e in examples if not any(jaccard(set(tokenize(e["question"])), b) >= 0.6 for b in bench)]
    log("8 benchmark decontamination (question Jaccard >= 0.6)", len(examples), len(keep))
    examples = keep

    for e in examples:  # group split: every example from one source section/problem lands in the same split
        bucket = int(hashlib.sha256(f"{SEED}|{e['group']}".encode()).hexdigest(), 16) % 100
        e["split"] = "train" if bucket < 80 else ("val" if bucket < 90 else "test")
    log("9 leakage-safe grouped split 80/10/10", len(examples), len(examples),
        sizes=dict(Counter(e["split"] for e in examples)))
    return examples, rep


def to_record(e: dict, i: int) -> dict:
    msgs = build_messages(e["question"], e["hits"], e["mode"], "medium", None, 50)
    msgs.append({"role": "assistant", "content": e["answer"]})
    return {"id": f"ex{i:05d}", "type": e["type"], "mode": e["mode"], "split": e["split"], "source": e["source"],
            "messages": msgs, "meta": e["meta"]}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--teacher", help="Ollama base URL to let a local LLM write corpus answers")
    ap.add_argument("--teacher-model", default="qwen3:14b")
    args = ap.parse_args()
    rng = random.Random(SEED)
    rag.reset()
    rag.ingest_all(dense=False)
    rows, _ = rag.build_rows()
    raw = gen_corpus(rows, rng) + gen_worked(rows, rng) + gen_abstain(rows, rng) + gen_quiz(rows, rng)
    if args.teacher:
        print("teacher answers written:", teacher_answers(raw, args.teacher, args.teacher_model, rng))
    benchmark = json.loads((ROOT / "backend" / "data" / "benchmarks" / "os_questions.json").read_text("utf-8"))
    rng.shuffle(raw)
    raw_counts = Counter(e["type"] for e in raw)
    final, report = preprocess(raw, benchmark)
    records = [to_record(e, i) for i, e in enumerate(final)]

    OUT.mkdir(parents=True, exist_ok=True)
    for split in ("train", "val", "test"):
        with open(OUT / f"{split}.jsonl", "w", encoding="utf-8") as fh:
            for r in records:
                if r["split"] == split:
                    fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    toks = [sum(len(m["content"]) for m in r["messages"]) // 4 for r in records]
    report.update({
        "seed": SEED, "raw_examples": sum(raw_counts.values()), "final_examples": len(records), "raw_by_type": dict(raw_counts),
        "final_by_type": dict(Counter(r["type"] for r in records)), "final_by_mode": dict(Counter(r["mode"] for r in records)),
        "final_by_split": dict(Counter(r["split"] for r in records)),
        "abstention_share": round(sum(1 for r in records if r["meta"].get("abstain")) / len(records), 3),
        "approx_tokens": {"mean": round(sum(toks) / len(toks)), "max": max(toks), "p95": sorted(toks)[int(0.95 * len(toks))]},
        "corpus_sections": len({r["id"] for r in rows}), "teacher_used": bool(args.teacher),
    })
    (OUT / "preprocessing_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    card = f"""# OSTutor fine-tuning dataset

Original, generated for this project (see `training/build_dataset.py`). Nothing is scraped from third-party sources.

| split | examples |
|---|---|
""" + "\n".join(f"| {k} | {v} |" for k, v in sorted(report["final_by_split"].items())) + """

Example types: corpus_teach / corpus_exam / corpus_socratic / corpus_define (restructured sections of the project corpus),
worked_* (numeric problems whose answers are computed by the simulators), quiz_explain (question-bank explanations),
abstain_offtopic / abstain_nearmiss (the tutor declines when the evidence does not contain the answer).

Every record is a 3-message chat (system, user with numbered EVIDENCE and QUESTION, assistant) built by the application's own
prompt builder, so the fine-tuned model sees exactly what it will see at serving time. Splits are grouped by source section or
problem so no section leaks across splits, and benchmark questions are decontaminated from the training data.
Preprocessing counts per stage: `preprocessing_report.json`.
"""
    (OUT / "DATASET_CARD.md").write_text(card, encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("raw_examples", "final_examples", "final_by_split", "final_by_type", "abstention_share", "approx_tokens")}, indent=1))
    for s in report["stages"]:
        print(f"{s['stage']:<58} {s['before']:>5} -> {s['after']:<5} (-{s['removed']})")


if __name__ == "__main__":
    main()
