#!/usr/bin/env python3
"""QLoRA fine-tuning of Qwen3 for OSTutor: 4-bit base model, LoRA adapters, loss on the assistant answer only.

Needs a CUDA GPU (about 10 GB for the 8B model, 16 GB+ for the 14B). Install: pip install -r training/requirements-train.txt
    python training/train_qlora.py --base Qwen/Qwen3-8B --out training/outputs/ostutor-lora
Uses plain transformers.Trainer (no TRL), so it is not sensitive to TRL API changes.
"""
from __future__ import annotations

import argparse
import inspect
import json
import math
import random
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET_MODULES = ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text("utf-8").splitlines() if line.strip()]


def render(tokenizer, messages: list[dict]) -> tuple[str, str]:
    """(prompt text, answer text). The prompt ends exactly where generation starts at serving time."""
    prompt = tokenizer.apply_chat_template(messages[:-1], tokenize=False, add_generation_prompt=True, enable_thinking=False)
    return prompt, messages[-1]["content"] + tokenizer.eos_token


def build_features(tokenizer, record: dict, max_len: int) -> dict | None:
    """Tokenise one record. Prompt tokens get label -100 so only the answer is learned. Over-long examples are dropped, never truncated."""
    prompt, answer = render(tokenizer, record["messages"])
    p = tokenizer(prompt, add_special_tokens=False)["input_ids"]
    a = tokenizer(answer, add_special_tokens=False)["input_ids"]
    if len(p) + len(a) > max_len:
        return None
    return {"input_ids": p + a, "attention_mask": [1] * (len(p) + len(a)), "labels": [-100] * len(p) + a}


class Collator:
    def __init__(self, pad_id: int):
        self.pad_id = pad_id

    def __call__(self, batch: list[dict]) -> dict:
        import torch

        n = max(len(b["input_ids"]) for b in batch)
        pad = lambda key, val: torch.tensor([b[key] + [val] * (n - len(b[key])) for b in batch])  # noqa: E731
        return {"input_ids": pad("input_ids", self.pad_id), "attention_mask": pad("attention_mask", 0), "labels": pad("labels", -100)}


class ListDataset:
    def __init__(self, items: list[dict]):
        self.items = items

    def __len__(self) -> int:
        return len(self.items)

    def __getitem__(self, i: int) -> dict:
        return self.items[i]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="Qwen/Qwen3-8B")
    ap.add_argument("--data", default=str(ROOT / "training" / "data" / "processed"))
    ap.add_argument("--out", default=str(ROOT / "training" / "outputs" / "ostutor-lora"))
    ap.add_argument("--epochs", type=float, default=3)
    ap.add_argument("--lr", type=float, default=2e-4)
    ap.add_argument("--batch", type=int, default=2)
    ap.add_argument("--grad-accum", type=int, default=8)
    ap.add_argument("--max-len", type=int, default=2048)
    ap.add_argument("--rank", type=int, default=16)
    ap.add_argument("--alpha", type=int, default=32)
    ap.add_argument("--dropout", type=float, default=0.05)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    import torch
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig, Trainer, TrainingArguments, set_seed

    if not torch.cuda.is_available():
        raise SystemExit("A CUDA GPU is required for QLoRA training. Use Google Colab/Kaggle (see training/colab_finetune.ipynb).")
    set_seed(args.seed)
    random.seed(args.seed)
    tok = AutoTokenizer.from_pretrained(args.base)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    data = Path(args.data)
    feats = {}
    for split in ("train", "val"):
        recs = load_jsonl(data / f"{split}.jsonl")
        built = [f for f in (build_features(tok, r, args.max_len) for r in recs) if f]
        print(f"{split}: {len(built)}/{len(recs)} examples fit in {args.max_len} tokens")
        feats[split] = ListDataset(built)

    bf16 = torch.cuda.is_bf16_supported()
    bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True,
                             bnb_4bit_compute_dtype=torch.bfloat16 if bf16 else torch.float16)
    model = AutoModelForCausalLM.from_pretrained(args.base, quantization_config=bnb, device_map="auto")
    model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)
    model = get_peft_model(model, LoraConfig(r=args.rank, lora_alpha=args.alpha, lora_dropout=args.dropout, bias="none",
                                             task_type="CAUSAL_LM", target_modules=TARGET_MODULES))
    trainable, total = sum(p.numel() for p in model.parameters() if p.requires_grad), sum(p.numel() for p in model.parameters())
    print(f"trainable parameters: {trainable:,} of {total:,} ({100 * trainable / total:.2f}%)")

    steps_per_epoch = max(1, math.ceil(len(feats["train"]) / (args.batch * args.grad_accum)))
    eval_steps = max(10, steps_per_epoch // 2)
    kwargs = dict(output_dir=args.out, num_train_epochs=args.epochs, per_device_train_batch_size=args.batch,
                  per_device_eval_batch_size=args.batch, gradient_accumulation_steps=args.grad_accum, learning_rate=args.lr,
                  lr_scheduler_type="cosine", warmup_ratio=0.05, weight_decay=0.0, logging_steps=10, save_steps=eval_steps,
                  eval_steps=eval_steps, save_strategy="steps", save_total_limit=2, load_best_model_at_end=True,
                  metric_for_best_model="eval_loss", greater_is_better=False, bf16=bf16, fp16=not bf16,
                  gradient_checkpointing=True, group_by_length=False, report_to="none", seed=args.seed,
                  remove_unused_columns=False, optim="paged_adamw_8bit")
    key = "eval_strategy" if "eval_strategy" in inspect.signature(TrainingArguments.__init__).parameters else "evaluation_strategy"
    kwargs[key] = "steps"
    trainer = Trainer(model=model, args=TrainingArguments(**kwargs), train_dataset=feats["train"], eval_dataset=feats["val"],
                      data_collator=Collator(tok.pad_token_id))
    started = time.time()
    result = trainer.train()
    metrics = trainer.evaluate()
    trainer.save_model(args.out)
    tok.save_pretrained(args.out)
    summary = {"base_model": args.base, "train_examples": len(feats["train"]), "val_examples": len(feats["val"]),
               "trainable_parameters": trainable, "epochs": args.epochs, "learning_rate": args.lr, "lora_rank": args.rank,
               "train_loss": result.training_loss, "eval_loss": metrics.get("eval_loss"),
               "eval_perplexity": math.exp(metrics["eval_loss"]) if metrics.get("eval_loss") is not None else None,
               "minutes": round((time.time() - started) / 60, 1),
               "log_history": trainer.state.log_history}
    (Path(args.out) / "training_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print("saved adapter to", args.out, "| eval loss", metrics.get("eval_loss"))


if __name__ == "__main__":
    main()
