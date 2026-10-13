# Evaluation

Reproduce everything offline: `python scripts/verify.py`. In the app: **Knowledge → Evaluation**.

## Retrieval (sparse path, 105 chunks, 40 in-scope questions + 5 off-topic probes)
| Variant | Recall@5 | MRR | nDCG@5 | Hit@1 |
|---|---|---|---|---|
| BM25 only | 1.000 | 0.983 | 0.991 | 0.975 |
| TF-IDF (uni+bigram) only | 0.992 | 0.988 | 0.982 | 0.975 |
| BM25 + TF-IDF fused, no expansion | 1.000 | 0.971 | 0.980 | 0.950 |
| + glossary expansion | 1.000 | 0.988 | 0.991 | 0.975 |
| + MMR (shipped) | 1.000 | 0.988 | 0.991 | 0.975 |

Honest reading: the benchmark is saturated. It was written alongside the corpus by the same author, the corpus is small and each
topic has its own file, so even BM25 alone nearly maxes it; differences of 0.01–0.02 are one question. These numbers show there is no
regression and that fusion/expansion do not hurt — they do **not** demonstrate that dense retrieval or reranking help. That needs a
harder, independently written benchmark and a real embedding model (not available where this was built). Median query latency
0.63 ms (sparse, p95 0.89 ms).

Abstention: 0 of 40 in-scope questions wrongly declined; 4 of 5 off-topic probes declined (the miss: "Explain how quantum computing works",
IDF-weighted coverage 0.41 vs threshold 0.40). With the cross-encoder active the decision also uses the reranker score.

## Answers
`POST /api/evaluation/run` generates answers with the configured model and reports citation correctness, groundedness (answer terms found
in evidence), concept coverage and the per-sentence evidence-support score. Run it before and after fine-tuning to compare models, or use
`training/evaluate_models.py` for a judge-free comparison on the held-out test split.

## Simulators
`backend/tests/test_simulators.py` asserts textbook results: FCFS/SJF/RR waiting times for the 24/3/3 example, FIFO/LRU/OPT = 15/12/9
page faults, Belady’s anomaly (9→10 faults), the Banker’s safe sequence P1,P3,P4,P0,P2, and disk totals 640/236/331/382/299/322.
