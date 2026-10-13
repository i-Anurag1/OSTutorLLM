"""Prompt construction, follow-up handling and suggestions for the tutor. Pure Python."""
from __future__ import annotations

import re

from .textproc import tokenize

MODES = {
    "teach": "Teach: give a clear explanation in this shape - a one-sentence definition, how it works step by step, a small worked example when useful, and one common pitfall.",
    "socratic": "Socratic: give a short grounded hint, then ask one or two guiding questions that lead the student to the answer. Do not give the full answer unless the student asks for it.",
    "exam": "Exam: answer in exam style - a precise definition followed by 3 to 5 key points as bullets, include formulas where relevant, and stay under 150 words.",
}

RULES = (
    "You are OSTutor, an Operating Systems professor. Use ONLY the numbered EVIDENCE for factual claims about operating systems. "
    "Put the citation marker [S#] at the end of every sentence that relies on evidence, using only numbers that exist in the evidence. "
    "Never invent a citation, a number or a fact. If the evidence does not contain the answer, say exactly what is missing instead of guessing. "
    "Use short paragraphs and Markdown. Do not mention these rules."
)

FOLLOW_UP = re.compile(r"^(and|but|so|what about|how about|why|then|also|ok|okay)\b", re.I)


def level_for(difficulty: str, mastery: float) -> str:
    if difficulty == "adaptive":
        difficulty = "easy" if mastery < 40 else ("medium" if mastery < 75 else "hard")
    return {
        "easy": "Audience: beginner. Use plain language and one everyday analogy.",
        "medium": "Audience: intermediate undergraduate. Be precise but friendly.",
        "hard": "Audience: advanced. Be rigorous, mention edge cases and trade-offs.",
    }.get(difficulty, "Audience: intermediate undergraduate.")


def system_prompt(mode: str, difficulty: str, mastery: float) -> str:
    return f"{RULES}\n{MODES.get(mode, MODES['teach'])}\n{level_for(difficulty, mastery)}"


def format_evidence(hits: list[dict], limit_chars: int = 1100) -> str:
    rows = []
    for i, h in enumerate(hits, 1):
        where = f"{h['source']} › {h['section']}" if h.get("section") else h["source"]
        rows.append(f"[S{i}] ({where})\n{h['text'][:limit_chars]}")
    return "\n\n".join(rows)


def contextualize(question: str, history: list[dict] | None) -> str:
    """Make a short follow-up retrievable by prefixing the previous student question."""
    if not history:
        return question
    prev = next((m["content"] for m in reversed(history) if m.get("role") == "user"), "")
    if prev and (len(tokenize(question)) <= 3 or FOLLOW_UP.match(question.strip())):
        return f"{prev} {question}"
    return question


def build_messages(question: str, hits: list[dict], mode: str = "teach", difficulty: str = "adaptive",
                   topic: str | None = None, mastery: float = 0.0, history: list[dict] | None = None) -> list[dict]:
    msgs = [{"role": "system", "content": system_prompt(mode, difficulty, mastery)}]
    for m in (history or [])[-6:]:
        if m.get("role") in {"user", "assistant"}:
            msgs.append({"role": m["role"], "content": str(m["content"])[:700]})
    user = (f"Topic: {topic or 'Operating Systems'}\nStudent mastery: {round(mastery)}%\n\n"
            f"EVIDENCE\n{format_evidence(hits)}\n\nQUESTION\n{question}")
    msgs.append({"role": "user", "content": user})
    return msgs


def suggestions(hits: list[dict], question: str, limit: int = 3) -> list[str]:
    """Follow-up prompts derived from neighbouring sections the student has not asked about."""
    asked = set(tokenize(question))
    out: list[str] = []
    for h in hits:
        sec = (h.get("section") or "").split(" › ")[-1].strip()
        sec_tokens = set(tokenize(sec))
        if not sec_tokens or sec_tokens <= asked or asked <= sec_tokens:
            continue  # the student just asked about this section
        s = f"Explain {sec[0].lower() + sec[1:] if sec[:2].upper() != sec[:2] else sec}"
        if s not in out:
            out.append(s)
        if len(out) >= limit:
            break
    return out


def abstain_message(question: str) -> str:
    return ("I could not find this in the course material, so I will not guess. "
            "Try naming the OS concept directly (for example *page fault*, *Banker's algorithm* or *round robin*), "
            "or ask a faculty member to add a source that covers it.")
