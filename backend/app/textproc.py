"""Shared, dependency-free text processing used by retrieval, grounding and evaluation."""
from __future__ import annotations

import re

_TOKEN = re.compile(r"[a-z0-9]+")
_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\[(])")

STOPWORDS = frozenset(
    """a an the and or but if then else of to in on at by for with from as is are was were be been being it its
    this that these those there here what which who whom whose when where why how can could should would may might
    will shall do does did done have has had not no nor so than too very just also into onto over under about after
    before between during each other such only own same both few more most some any all one two use used using uses
    explain describe compare comparison difference differences tell give example examples please define definition
    meaning mean means work works working versus vs happen happens happened make makes made get gets got show shows know way ways thing things kind work works me my you your i we us they them their he she his her""".split()
)

# Abbreviation <-> expansion pairs for the Operating Systems domain.
GLOSSARY = {
    "fcfs": "first come first served", "sjf": "shortest job first", "srtf": "shortest remaining time first",
    "rr": "round robin", "mlfq": "multilevel feedback queue", "lru": "least recently used",
    "fifo": "first in first out", "opt": "optimal", "tlb": "translation lookaside buffer",
    "mmu": "memory management unit", "pcb": "process control block", "cow": "copy on write",
    "ipc": "inter process communication", "dma": "direct memory access",
    "raid": "redundant array of independent disks", "sstf": "shortest seek time first",
    "cscan": "circular scan", "clook": "circular look", "aslr": "address space layout randomisation",
    "acl": "access control list", "fat": "file allocation table", "oom": "out of memory killer",
    "ssd": "solid state drive", "os": "operating system", "mutex": "mutual exclusion lock",
    "pthread": "posix threads", "syscall": "system call", "inode": "index node",
}
# Phrase -> related keywords that commonly co-occur in good answers.
CONCEPT_LINKS = {
    "page fault": "demand paging valid bit", "deadlock": "coffman circular wait", "safe state": "banker safety algorithm",
    "starvation": "aging", "convoy": "fcfs", "belady": "fifo anomaly frames", "thrashing": "working set",
    "semaphore": "wait signal", "mutex": "lock critical section", "race": "critical section",
    "inode": "file metadata pointer", "fork": "child process exec wait", "virtual memory": "demand paging",
    "quantum": "round robin", "elevator": "scan", "seek": "disk head cylinder", "fragmentation": "hole compaction",
    "buffer overflow": "stack canary aslr", "context switch": "pcb", "producer": "bounded buffer semaphore",
    "philosopher": "forks deadlock", "paging": "page table frame", "segment": "base limit",
}


def stem(word: str) -> str:
    """Conservative suffix stripper (schedules/scheduling/scheduler -> schedul)."""
    w = word
    if len(w) <= 3 or w.isdigit():
        return w
    if w.endswith("ies") and len(w) > 4:
        w = w[:-3] + "y"
    elif w.endswith(("sses", "xes", "ches", "shes", "zes")):
        w = w[:-2]
    elif w.endswith("s") and not w.endswith(("ss", "us", "is")):
        w = w[:-1]
    for _ in range(2):
        for suf, floor in (("ing", 3), ("ed", 4), ("er", 4)):
            if w.endswith(suf) and len(w) - len(suf) >= floor:
                w = w[: -len(suf)]
                if len(w) > 2 and w[-1] == w[-2] and w[-1] not in "ls":
                    w = w[:-1]
                break
        else:
            break
    if w.endswith("e") and len(w) > 3:
        w = w[:-1]
    return w


def tokenize(text: str, drop_stop: bool = True, do_stem: bool = True) -> list[str]:
    out = []
    for raw in _TOKEN.findall(text.lower()):
        if drop_stop and raw in STOPWORDS:
            continue
        out.append(stem(raw) if do_stem else raw)
    return out


def salient_terms(text: str) -> set[str]:
    return {t for t in tokenize(text) if len(t) > 1}


def sentences(text: str) -> list[str]:
    out: list[str] = []
    for block in re.split(r"\n+", text):
        block = block.strip()
        if block:
            out.extend(s.strip() for s in _SENT_SPLIT.split(block) if s.strip())
    return out


def expand_query(query: str) -> tuple[str, list[str]]:
    """Add domain synonyms. Returns (expanded query, list of added phrases)."""
    low = query.lower().replace("-", "")
    words = set(_TOKEN.findall(low))
    added: list[str] = []
    for abbr, full in GLOSSARY.items():
        if abbr in words:
            added.append(full)
        elif full in low and abbr not in words:
            added.append(abbr)
    for phrase, extra in CONCEPT_LINKS.items():
        if phrase in low:
            added.append(extra)
    return (query + " " + " ".join(added)).strip(), added
