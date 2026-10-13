import os
import unittest

from app.code_runner import check_python, run_python, run_shell
from app.exercises import EXERCISES


class Python(unittest.TestCase):
    def test_hello(self):
        r = run_python("print('hi', 2 + 2)")
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["stdout"].strip(), "hi 4")

    def test_blocked_imports_and_reflection(self):
        for src in ("import os", "import subprocess", "from sys import exit", "import socket", "__import__('os')",
                    "eval('1')", "open('/etc/passwd')", "().__class__.__bases__", "getattr(1, 'real')",
                    "'{0.__class__}'.format(1)"):
            self.assertIsNotNone(check_python(src), src)
            self.assertFalse(run_python(src)["ok"], src)

    def test_allowed_features(self):
        src = ("import math, threading, queue\nfrom collections import deque\n"
               "class A:\n    def __init__(self): self.x = 1\n    def __repr__(self): return 'A'\n"
               "if __name__ == '__main__':\n    print(math.sqrt(16), A(), deque([1]))\n")
        r = run_python(src)
        self.assertTrue(r["ok"], r)
        self.assertIn("4.0 A deque([1])", r["stdout"])

    def test_syntax_error_reported(self):
        r = run_python("print(")
        self.assertFalse(r["ok"])
        self.assertIn("SyntaxError", r["stderr"])

    def test_timeout_kills_infinite_loop(self):
        r = run_python("while True:\n    pass", timeout=1)
        self.assertTrue(r["timed_out"] or r["exit_code"] != 0)
        self.assertLess(r["duration_ms"], 4000)

    def test_memory_limit(self):
        r = run_python("x = bytearray(1024 * 1024 * 2000)\nprint(len(x))", timeout=3)
        self.assertFalse(r["ok"])

    def test_output_is_capped(self):
        r = run_python("for i in range(200000):\n    print('x' * 50)", timeout=3)
        self.assertLessEqual(len(r["stdout"]), 10000)

    def test_runtime_error_exit_code(self):
        r = run_python("1/0")
        self.assertFalse(r["ok"])
        self.assertIn("ZeroDivisionError", r["stderr"])


class Shell(unittest.TestCase):
    def test_pipe_and_loop(self):
        self.assertEqual(run_shell("printf 'a\\nb\\n' | wc -l")["stdout"].strip(), "2")
        self.assertEqual(run_shell("t=0; for i in 1 2 3; do t=$((t+i)); done; echo $t")["stdout"].strip(), "6")

    def test_forbidden(self):
        for script in ("curl http://example.com", "wget x", "cd /", "echo hi > out.txt", "/bin/ls", "python3 -c 1",
                       "bash -c 'echo x'", "env", "cat /proc/1/environ", "exec ls", "sed -n p"):
            r = run_shell(script)
            self.assertFalse(r["ok"], script)

    def test_timeout(self):
        r = run_shell("sleep 5", timeout=1)
        self.assertTrue(r["timed_out"])


class Exercises(unittest.TestCase):
    def test_every_solution_passes_its_own_test(self):
        for ex in EXERCISES:
            r = (run_python if ex["language"] == "python" else run_shell)(ex["solution"])
            self.assertTrue(r["ok"], (ex["id"], r))
            self.assertEqual(r["stdout"].strip(), ex["expected_stdout"].strip(), ex["id"])

    def test_starters_do_not_already_pass(self):
        for ex in EXERCISES:
            r = (run_python if ex["language"] == "python" else run_shell)(ex["starter"])
            self.assertNotEqual(r["stdout"].strip(), ex["expected_stdout"].strip(), ex["id"])


if __name__ == "__main__":
    unittest.main()
