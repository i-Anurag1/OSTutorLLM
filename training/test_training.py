"""Tests for the dataset pipeline and training helpers.  Run:  python training/test_training.py"""
import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "training" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


bd = load("build_dataset")
ev = load("evaluate_models")
tq = load("train_qlora")
PROC = ROOT / "training" / "data" / "processed"
BENCH = json.loads((ROOT / "backend" / "data" / "benchmarks" / "os_questions.json").read_text("utf-8"))
HIT = {"id": "a#0", "path": "a.md", "source": "a.md", "section": "FCFS", "text": "FCFS runs processes in arrival order. It suffers from the convoy effect."}


def ex(question="Explain the thing please.", answer="FCFS runs processes in arrival order [S1]. It suffers from the convoy effect [S1].",
       kind="corpus_teach", group="g", **meta):
    meta.setdefault("cited", [1])
    return {"type": kind, "mode": "teach", "source": "a.md", "group": group, "question": question, "hits": [dict(HIT)], "answer": answer, "meta": meta}


def stage(rep, prefix):
    return next(s for s in rep["stages"] if s["stage"].startswith(prefix))


class Stages(unittest.TestCase):
    def test_normalisation_and_scrub(self):
        self.assertEqual(bd.normalize("It\u2019s  a \u201cdemo\u201d\u00a0text \u2014 ok\u200b\n\n\n\nnext"), 'It\'s a "demo" text - ok\n\nnext')
        text, n = bd.scrub("mail me at a.b@example.com or see https://x.org/p, id 12345678901")
        self.assertEqual((text, n), ("mail me at [email] or see [link], id [number]", 3))

    def test_every_filter_removes_what_it_should(self):
        good = ex(question="Explain how convoy effect works in FCFS scheduling.", group="g1")
        bad = [
            ex(question="Explain a long wrong citation question here.", answer="FCFS runs processes in arrival order [S7].", group="g2"),  # invalid id
            ex(question="Explain unicode answer text for this check.", answer="FCFS runs processes in arrival order \u4e2d\u6587\u4e2d\u6587\u4e2d\u6587\u4e2d\u6587\u4e2d\u6587 [S1].", group="g3"),
            ex(question="Explain a tiny answer problem for the filter.", answer="Yes.", group="g4"),
            ex(question="Explain unsupported claims about fruit here.", answer="Bananas are yellow and grow on tall tropical plants near rivers [S1].", group="g5"),
            ex(question="Tell me about abstention with a stray citation.", answer="I could not find this in the course material [S1].", group="g6", abstain=True),
            dict(good, group="g1b"),  # exact duplicate
            ex(question="Explain how convoy effect works in FCFS scheduling.", answer="FCFS runs processes in arrival order [S1]. It suffers from the convoy effect [S1]!", group="g7"),  # near duplicate
        ]
        final, rep = bd.preprocess([good] + bad, BENCH)
        self.assertEqual([e["group"] for e in final], ["g1"])
        self.assertEqual(stage(rep, "3")["removed"], 2)
        self.assertEqual(stage(rep, "4")["removed"], 2)
        self.assertEqual(stage(rep, "5")["removed"], 1)
        self.assertEqual(stage(rep, "6")["removed"], 1)
        self.assertEqual(stage(rep, "7")["removed"], 1)

    def test_benchmark_decontamination(self):
        leaked = ex(question=BENCH[0]["question"], group="gb")
        final, rep = bd.preprocess([leaked], BENCH)
        self.assertEqual(final, [])
        self.assertEqual(stage(rep, "8")["removed"], 1)

    def test_split_is_grouped_and_deterministic(self):
        items = [ex(question=f"Explain distinct topic number {i} in detail please.", answer=f"FCFS runs processes in arrival order [S1]. Variation {i} adds the convoy effect [S1].", group=f"grp{i % 7}") for i in range(60)]
        a, _ = bd.preprocess(items, BENCH)
        b, _ = bd.preprocess([json.loads(json.dumps(i)) for i in items], BENCH)
        self.assertEqual([e["split"] for e in a], [e["split"] for e in b])
        by_group = {}
        for e in a:
            by_group.setdefault(e["group"], set()).add(e["split"])
        self.assertTrue(all(len(s) == 1 for s in by_group.values()))


class ShippedDataset(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = {s: [json.loads(l) for l in (PROC / f"{s}.jsonl").read_text("utf-8").splitlines() if l.strip()] for s in ("train", "val", "test")}

    def test_sizes_and_report(self):
        rep = json.loads((PROC / "preprocessing_report.json").read_text("utf-8"))
        self.assertEqual(sum(len(v) for v in self.rows.values()), rep["final_examples"])
        self.assertGreaterEqual(len(self.rows["train"]), 500)
        self.assertEqual(len(rep["stages"]), 9)

    def test_record_format_and_citations(self):
        for split, rows in self.rows.items():
            for r in rows:
                roles = [m["role"] for m in r["messages"]]
                self.assertEqual(roles, ["system", "user", "assistant"], r["id"])
                n_ev = len(ev.evidence_of(r))
                used = [int(x) for x in ev.CITE_RE.findall(r["messages"][-1]["content"])]
                self.assertTrue(all(1 <= u <= n_ev for u in used), r["id"])
                if r["meta"].get("abstain"):
                    self.assertEqual(used, [], r["id"])
                self.assertEqual(r["split"], split)

    def test_no_group_or_benchmark_leakage(self):
        seen = {}
        for split, rows in self.rows.items():
            for r in rows:
                q = r["messages"][1]["content"].split("QUESTION\n")[-1]
                self.assertFalse(any(bd.jaccard(set(bd.tokenize(q)), set(bd.tokenize(b["question"]))) >= 0.6 for b in BENCH), q)
        for split, rows in self.rows.items():
            for r in rows:
                seen.setdefault(r["source"] + "|" + str(r["meta"].get("reference", "")) + r["messages"][1]["content"][:0], set()).add(split)

    def test_all_types_present_in_train(self):
        types = {r["type"] for r in self.rows["train"]}
        for t in ("corpus_teach", "corpus_exam", "corpus_socratic", "worked_cpu", "worked_page", "worked_disk", "worked_banker", "abstain_offtopic", "abstain_nearmiss", "quiz_explain"):
            self.assertIn(t, types)

    def test_worked_references_match_answer_text(self):
        for rows in self.rows.values():
            for r in rows:
                if r["type"].startswith("worked"):
                    self.assertEqual(ev.final_answer(r["messages"][-1]["content"]), str(r["meta"]["reference"]).lower())


class Scoring(unittest.TestCase):
    def test_references_score_perfectly_and_baselines_do_not(self):
        recs = self.rows = [json.loads(l) for l in (PROC / "test.jsonl").read_text("utf-8").splitlines() if l.strip()]
        ref = ev.summarise([(r, ev.score_output(r, r["messages"][-1]["content"])) for r in recs])
        self.assertEqual(ref["valid_citation_rate"], 1.0)
        self.assertEqual(ref["worked_exact_match"], 1.0)
        self.assertEqual(ref["abstention_accuracy"], 1.0)
        bad = ev.summarise([(r, ev.score_output(r, "Operating systems are great [S9].")) for r in recs])
        self.assertEqual(bad["valid_citation_rate"], 0.0)
        self.assertEqual(bad["worked_exact_match"], 0.0)


class FakeTok:
    """Character-level tokenizer with a ChatML-like template, enough to test label masking without downloading a model."""
    eos_token = "<E>"

    def apply_chat_template(self, messages, tokenize=False, add_generation_prompt=False, enable_thinking=True):
        return "".join(f"<{m['role']}>{m['content']}<E>" for m in messages) + ("<assistant>" if add_generation_prompt else "")

    def __call__(self, text, add_special_tokens=False):
        return {"input_ids": [ord(c) for c in text]}


class Features(unittest.TestCase):
    def test_only_answer_tokens_have_labels(self):
        rec = {"messages": [{"role": "system", "content": "S"}, {"role": "user", "content": "Q"}, {"role": "assistant", "content": "ANS"}]}
        f = tq.build_features(FakeTok(), rec, 100)
        n_prompt = len("<system>S<E><user>Q<E><assistant>")
        self.assertTrue(all(x == -100 for x in f["labels"][:n_prompt]))
        self.assertEqual("".join(chr(x) for x in f["labels"][n_prompt:]), "ANS<E>")
        self.assertEqual(len(f["input_ids"]), len(f["labels"]))

    def test_overlong_examples_are_dropped_not_truncated(self):
        rec = {"messages": [{"role": "user", "content": "x" * 50}, {"role": "assistant", "content": "y" * 50}]}
        self.assertIsNone(tq.build_features(FakeTok(), rec, 60))

    def test_real_records_fit_context(self):
        rows = [json.loads(l) for l in (PROC / "train.jsonl").read_text("utf-8").splitlines()[:50]]
        self.assertTrue(all(tq.build_features(FakeTok(), r, 6000) for r in rows))


if __name__ == "__main__":
    unittest.main(verbosity=1)
