# OSTutor fine-tuning dataset

Original, generated for this project (see `training/build_dataset.py`). Nothing is scraped from third-party sources.

| split | examples |
|---|---|
| test | 91 |
| train | 647 |
| val | 88 |

Example types: corpus_teach / corpus_exam / corpus_socratic / corpus_define (restructured sections of the project corpus),
worked_* (numeric problems whose answers are computed by the simulators), quiz_explain (question-bank explanations),
abstain_offtopic / abstain_nearmiss (the tutor declines when the evidence does not contain the answer).

Every record is a 3-message chat (system, user with numbered EVIDENCE and QUESTION, assistant) built by the application's own
prompt builder, so the fine-tuned model sees exactly what it will see at serving time. Splits are grouped by source section or
problem so no section leaks across splits, and benchmark questions are decontaminated from the training data.
Preprocessing counts per stage: `preprocessing_report.json`.
