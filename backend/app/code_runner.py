"""Sandboxed runners for the Python and shell labs.

Defence in depth (best effort, designed for a classroom lab, not for hostile multi-tenant hosting):
  * Python: static AST screening with an import allow-list and banned reflection helpers.
  * Shell: restricted bash (no cd, no redirection, no slashes in command names) whose PATH contains symlinks
    to a small allow-list of binaries only.
  * Processes run in their own session, as an unprivileged user when started as root, with CPU, memory,
    file-size, process-count and open-file limits, output captured to size-limited files, and a wall-clock
    timeout that kills the whole process group.
Run the API container without secrets mounted and keep it off sensitive networks.
"""
from __future__ import annotations

import ast
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time

try:
    import resource
except ImportError:  # Windows: the labs are only supported in the Linux container
    resource = None  # type: ignore[assignment]

ALLOWED_IMPORTS = {
    "math", "random", "collections", "itertools", "functools", "heapq", "bisect", "string", "re", "json", "typing",
    "dataclasses", "statistics", "threading", "queue", "enum", "copy", "textwrap", "decimal", "fractions",
    "operator", "datetime", "time", "abc", "array", "contextlib", "__future__",
}
BANNED_NAMES = {"eval", "exec", "compile", "open", "__import__", "globals", "locals", "vars", "getattr", "setattr",
                "delattr", "breakpoint", "exit", "quit", "memoryview", "help"}
SAFE_DUNDERS = {"__init__", "__name__", "__str__", "__repr__", "__enter__", "__exit__", "__len__", "__iter__",
                "__next__", "__eq__", "__lt__", "__le__", "__gt__", "__ge__", "__hash__", "__call__", "__getitem__",
                "__setitem__", "__contains__", "__add__", "__sub__", "__mul__", "__bool__", "__post_init__"}
BANNED_ATTRS = {"f_globals", "f_back", "f_builtins", "gi_frame", "cr_frame", "tb_frame", "gi_code", "func_globals"}
SHELL_ALLOWED = ["ls", "cat", "head", "tail", "wc", "sort", "uniq", "grep", "cut", "tr", "date", "whoami", "uname",
                 "basename", "dirname", "seq", "expr", "true", "false", "id", "ps", "stat", "diff", "cmp", "sleep",
                 "tee", "rev", "nl", "fold", "paste", "comm", "od", "md5sum", "sha256sum", "hostname", "printenv"]
SHELL_FORBIDDEN_TEXT = ["/proc", "/sys", "/dev/tcp", "/dev/udp", "/root", "/app"]
MAX_OUTPUT = 10_000
_bin_dir: str | None = None


def check_python(source: str) -> str | None:
    """Return a human-readable reason when the code is not allowed, else None."""
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        return f"SyntaxError: {e.msg} (line {e.lineno})"
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name.split(".")[0] not in ALLOWED_IMPORTS:
                    return f"Import of '{a.name}' is not allowed in the lab sandbox. Allowed: {', '.join(sorted(ALLOWED_IMPORTS - {'__future__'}))}"
        elif isinstance(node, ast.ImportFrom):
            if node.level or (node.module or "").split(".")[0] not in ALLOWED_IMPORTS:
                return f"Import from '{node.module or '.'}' is not allowed in the lab sandbox"
        elif isinstance(node, ast.Name) and node.id in BANNED_NAMES:
            return f"'{node.id}' is disabled in the lab sandbox"
        elif isinstance(node, ast.Attribute):
            if node.attr in BANNED_ATTRS or (node.attr.startswith("__") and node.attr.endswith("__") and node.attr not in SAFE_DUNDERS):
                return f"Access to '{node.attr}' is disabled in the lab sandbox"
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) and "__" in node.value and node.value != "__main__":
            return "Strings containing double underscores are disabled in the lab sandbox"
    return None


def _limits(timeout: int, memory_mb: int = 256):
    def apply() -> None:
        if resource is not None:
            cpu = max(1, int(timeout) + 1)
            for name, val in (("RLIMIT_CPU", (cpu, cpu)), ("RLIMIT_FSIZE", (1 << 20, 1 << 20)),
                              ("RLIMIT_NOFILE", (64, 64)), ("RLIMIT_NPROC", (64, 64)),
                              ("RLIMIT_AS", (memory_mb << 20, memory_mb << 20)), ("RLIMIT_CORE", (0, 0))):
                try:
                    resource.setrlimit(getattr(resource, name), val)
                except (ValueError, OSError):
                    pass
        if hasattr(os, "geteuid") and os.geteuid() == 0:  # never run student code as root
            os.setgid(65534)
            os.setuid(65534)
    return apply


def _execute(argv: list[str], timeout: int, cwd: str, env: dict) -> dict:
    started = time.perf_counter()
    with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
        proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=out, stderr=err, cwd=cwd, env=env,
                                preexec_fn=_limits(timeout) if os.name == "posix" else None, start_new_session=True)
        timed_out = False
        try:
            code = proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                proc.kill()
            code = proc.wait()
        out.seek(0)
        err.seek(0)
        stdout = out.read(MAX_OUTPUT + 1).decode("utf-8", "replace")
        stderr = err.read(MAX_OUTPUT + 1).decode("utf-8", "replace")
    if timed_out:
        stderr = (stderr + "\nExecution timed out").strip()
        code = 124
    elif code and code < 0:
        stderr = (stderr + f"\nProcess killed by signal {-code} (resource limit exceeded?)").strip()
    trunc = len(stdout) > MAX_OUTPUT or len(stderr) > MAX_OUTPUT
    return {"ok": code == 0 and not timed_out, "stdout": stdout[:MAX_OUTPUT], "stderr": stderr[:MAX_OUTPUT],
            "exit_code": code, "timed_out": timed_out, "truncated": trunc,
            "duration_ms": round((time.perf_counter() - started) * 1000, 1)}


def _blocked(reason: str, code: int = 126) -> dict:
    return {"ok": False, "stdout": "", "stderr": reason, "exit_code": code, "timed_out": False, "truncated": False, "duration_ms": 0.0}


def run_python(source: str, timeout: int = 3) -> dict:
    reason = check_python(source)
    if reason:
        return _blocked(reason, 1 if reason.startswith("SyntaxError") else 126)
    work = tempfile.mkdtemp(prefix="ostutor-py-")
    try:
        os.chmod(work, 0o755)
        path = os.path.join(work, "main.py")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(source)
        os.chmod(path, 0o644)
        env = {"PATH": "/usr/bin:/bin", "HOME": work, "LANG": "C.UTF-8", "PYTHONIOENCODING": "utf-8", "PYTHONHASHSEED": "0"}
        return _execute([sys.executable, "-I", "-B", path], timeout, work, env)
    finally:
        shutil.rmtree(work, ignore_errors=True)


def _sandbox_bin() -> str:
    global _bin_dir
    if _bin_dir and os.path.isdir(_bin_dir):
        return _bin_dir
    d = tempfile.mkdtemp(prefix="ostutor-bin-")
    for name in SHELL_ALLOWED:
        real = shutil.which(name)
        if real:
            os.symlink(real, os.path.join(d, name))
    os.chmod(d, 0o755)
    _bin_dir = d
    return d


def run_shell(script: str, timeout: int = 3) -> dict:
    if any(x in script for x in SHELL_FORBIDDEN_TEXT):
        return _blocked("Command blocked by sandbox policy (restricted path)")
    bash = shutil.which("bash")
    if not bash:
        return _blocked("bash is not available in this environment", 127)
    work = tempfile.mkdtemp(prefix="ostutor-sh-")
    try:
        os.chmod(work, 0o755)
        env = {"PATH": _sandbox_bin(), "HOME": work, "LANG": "C.UTF-8", "TERM": "dumb", "USER": "student", "PS1": "$ "}
        res = _execute([bash, "--restricted", "--noprofile", "--norc", "-c", script], timeout, work, env)
        if "restricted" in res["stderr"] or "command not found" in res["stderr"]:
            res["stderr"] += ("\nHint: the lab shell is restricted - it allows a fixed set of learning commands "
                              f"({', '.join(SHELL_ALLOWED[:12])}, ...), pipes, variables, loops and functions, but no cd or file redirection.")
        return res
    finally:
        shutil.rmtree(work, ignore_errors=True)
