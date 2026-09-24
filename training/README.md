# Optional QLoRA fine-tuning

Option 1 in the supplied case study is **RAG + Instruction-Tuned LLM**. The runnable application therefore uses the instruction-tuned Qwen3 14B model through local Ollama and does not falsely claim a fine-tuned checkpoint.

If the research paper later requires domain-specific fine-tuning, use the supplied corpus and a separately created instruction dataset with verified provenance. A real QLoRA run requires a suitable GPU and produces a new checkpoint; that checkpoint cannot be honestly embedded in this ZIP without actually training it.

Example training record format:
```json
{"instruction":"Explain process scheduling.","input":"","output":"..."}
```

Do not use copyrighted source text as training data unless the license permits it.
