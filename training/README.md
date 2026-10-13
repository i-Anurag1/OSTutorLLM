# Fine-tuning OSTutor

**Status, stated plainly.** This folder contains a complete, tested *pipeline* and an original, preprocessed dataset.
It does **not** contain trained weights: training needs a CUDA GPU and none was available where this project was
assembled. Nothing in the app claims a fine-tuned checkpoint exists; until you train one the app runs the stock model
(`LLM_MODEL=qwen3:14b`) and everything else (hybrid RAG, grounding checks, abstention) works the same.

## What fine-tuning is for here
Facts come from retrieval, not from the weights. Fine-tuning teaches *behaviour*: cite with `[S#]` using only ids that exist,
copy claims faithfully from evidence, decline when the evidence lacks the answer, follow the three modes (teach / Socratic /
exam), and compute worked problems step by step.

## The dataset (original, preprocessed)
`python training/build_dataset.py` -> `training/data/processed/{train,val,test}.jsonl` (+ `preprocessing_report.json`, `DATASET_CARD.md`).

| source | what it is |
|---|---|
| corpus | the project's own OS corpus restructured into teach / exam / Socratic / definition answers |
| worked | random numeric problems (CPU scheduling, page replacement, disk, paging, EAT, Banker's, segmentation) whose answers are **computed by `backend/app/simulators.py`**, so they are correct by construction |
| quiz | explanations from the authored question bank |
| abstain | off-topic and near-miss questions paired with *real* retrieval output; the correct answer is to decline |

Prompts are built by the app's own `tutor.build_messages` and evidence by the app's own retriever, so training matches serving.
Current build: **904 generated -> 826 kept** (647 train / 88 val / 91 test).

### Preprocessing stages (counts in the report)
1 Unicode (NFKC) and whitespace normalisation - 2 PII / link / long-number scrub - 3 length and ASCII-ratio filters -
4 citation integrity (every `[S#]` exists, abstentions carry none) - 5 groundedness (answer supported by the cited evidence) -
6 exact de-duplication - 7 near-duplicate removal (3-gram Jaccard >= 0.9) - 8 benchmark decontamination (training questions
too similar to `os_questions.json` are dropped) - 9 grouped 80/10/10 split (all examples from one source section stay in one split).
Stages 1-5 remove nothing from this generated data because it is clean by construction; `test_training.py` feeds each stage
deliberately bad records to prove it fires.

Limits worth knowing: corpus answers are restructured source sentences (good for citation and faithfulness behaviour, not for
rich pedagogy). For more natural answers run `build_dataset.py --teacher http://localhost:11434 --teacher-model qwen3:14b`: your
local LLM writes the answers and stages 4-5 reject the ungrounded ones. That mode could not be run here.

## Train on a free GPU
Open `colab_finetune.ipynb` in Google Colab (T4) or run locally with a CUDA GPU:
```
pip install -r training/requirements-train.txt
python training/train_qlora.py --base Qwen/Qwen3-8B          # ~10 GB VRAM; use Qwen/Qwen3-14B with 24 GB
python training/merge_and_export.py                          # merge LoRA, write Modelfile, print GGUF steps
ollama create ostutor-qwen3 -f training/outputs/ostutor-merged/Modelfile
```
Then set `LLM_MODEL=ostutor-qwen3` in `.env`. QLoRA 4-bit NF4, LoRA r=16 / alpha=32 on all attention and MLP projections,
cosine schedule, lr 2e-4, 3 epochs, loss on the assistant answer only, best checkpoint by validation loss.
The Modelfile's chat TEMPLATE mirrors the training format; if your Ollama version already imports the correct Qwen3 template
from the GGUF, delete the TEMPLATE block.

## Measure it
```
python training/evaluate_models.py --models qwen3:8b ostutor-qwen3 --limit 80
```
Reports valid-citation rate, citation rate, groundedness, abstention accuracy and exact match on computed problems/quiz answers
for each model on the held-out test split. `--selftest` scores the reference answers (all 1.0) and degenerate baselines (about 0)
to show the metrics discriminate.

## Tests
`python training/test_training.py` - 13 tests: every preprocessing stage, split determinism and leakage, shipped-dataset format,
metric scoring, and assistant-only label masking.
