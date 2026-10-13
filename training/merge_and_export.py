#!/usr/bin/env python3
"""Merge the LoRA adapter into the base model, write an Ollama Modelfile and print the GGUF conversion steps.

    python training/merge_and_export.py --base Qwen/Qwen3-8B --adapter training/outputs/ostutor-lora --out training/outputs/ostutor-merged
"""
import argparse
from pathlib import Path

MODELFILE = '''FROM ./ostutor-qwen3-q4_k_m.gguf
PARAMETER temperature 0.2
PARAMETER num_ctx 4096
PARAMETER stop "<|im_end|>"
TEMPLATE """{{- range $i, $_ := .Messages }}
{{- $last := eq (len (slice $.Messages $i)) 1 -}}
<|im_start|>{{ .Role }}
{{ .Content }}{{ if not $last }}<|im_end|>
{{ end }}
{{- if and $last (ne .Role "assistant") }}<|im_end|>
<|im_start|>assistant
<think>

</think>

{{ end }}
{{- end }}"""
'''


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="Qwen/Qwen3-8B")
    ap.add_argument("--adapter", default="training/outputs/ostutor-lora")
    ap.add_argument("--out", default="training/outputs/ostutor-merged")
    args = ap.parse_args()
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    dtype = torch.bfloat16 if torch.cuda.is_available() and torch.cuda.is_bf16_supported() else torch.float16
    model = AutoModelForCausalLM.from_pretrained(args.base, torch_dtype=dtype, device_map="auto" if torch.cuda.is_available() else "cpu")
    merged = PeftModel.from_pretrained(model, args.adapter).merge_and_unload()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    merged.save_pretrained(out, safe_serialization=True)
    AutoTokenizer.from_pretrained(args.base).save_pretrained(out)
    (out / "Modelfile").write_text(MODELFILE, encoding="utf-8")
    print(f"""
Merged model written to {out}. To serve it with Ollama:

  1. git clone https://github.com/ggml-org/llama.cpp && pip install -r llama.cpp/requirements.txt
  2. python llama.cpp/convert_hf_to_gguf.py {out} --outfile {out}/ostutor-qwen3-f16.gguf --outtype f16
  3. llama-quantize {out}/ostutor-qwen3-f16.gguf {out}/ostutor-qwen3-q4_k_m.gguf Q4_K_M
  4. cd {out} && ollama create ostutor-qwen3 -f Modelfile
  5. set LLM_MODEL=ostutor-qwen3 in .env and restart the API (docker compose up -d api)
""")


if __name__ == "__main__":
    main()
