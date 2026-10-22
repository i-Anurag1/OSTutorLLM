import json
import unittest
from unittest.mock import patch

from app.llm_utils import ThinkFilter, model_listed, parse_ollama_line, parse_openai_line, strip_think
from app.ratelimit import RateLimiter
from app import llm
from app.config import settings


class Think(unittest.TestCase):
    def test_strip(self):
        self.assertEqual(strip_think("<think>plan</think>Answer"), "Answer")
        self.assertEqual(strip_think("Hi <think>unfinished"), "Hi")
        self.assertEqual(strip_think("plain"), "plain")

    def test_stream_filter_across_chunks(self):
        f = ThinkFilter()
        out = "".join(f.feed(c) for c in ["Hel", "lo <thi", "nk>secret ", "stuff</th", "ink> world", "!"]) + f.flush()
        self.assertEqual(out, "Hello  world!")

    def test_false_tag_prefix_is_emitted(self):
        f = ThinkFilter()
        out = f.feed("a <t") + f.feed("able> b") + f.flush()
        self.assertEqual(out, "a <table> b")

    def test_unterminated_think_is_dropped(self):
        f = ThinkFilter()
        self.assertEqual(f.feed("x<think>never ends") + f.flush(), "x")


class Parsers(unittest.TestCase):
    def test_ollama(self):
        self.assertEqual(parse_ollama_line(json.dumps({"message": {"content": "Hi"}, "done": False})), ("Hi", False))
        self.assertEqual(parse_ollama_line(json.dumps({"done": True})), ("", True))
        self.assertEqual(parse_ollama_line("  "), ("", False))

    def test_openai(self):
        line = "data: " + json.dumps({"choices": [{"delta": {"content": "yo"}}]})
        self.assertEqual(parse_openai_line(line), ("yo", False))
        self.assertEqual(parse_openai_line("data: [DONE]"), ("", True))
        self.assertEqual(parse_openai_line(": keep-alive"), ("", False))

    def test_model_listed(self):
        self.assertTrue(model_listed("ostutor-qwen3", ["ostutor-qwen3:latest"]))
        self.assertTrue(model_listed("qwen3:14b", ["qwen3:14b"]))
        self.assertFalse(model_listed("qwen3:14b", ["qwen3:8b"]))


class Limiter(unittest.TestCase):
    def test_window(self):
        r = RateLimiter(2, 10)
        self.assertTrue(r.allow("a", 0))
        self.assertTrue(r.allow("a", 1))
        self.assertFalse(r.allow("a", 2))
        self.assertTrue(r.allow("b", 2))
        self.assertTrue(r.allow("a", 11))


class RequiredLLM(unittest.IsolatedAsyncioTestCase):
    async def test_required_llm_fails_instead_of_silent_fallback(self):
        old_base, old_required = settings.llm_base_url, settings.llm_required
        try:
            settings.llm_base_url = ""
            settings.llm_required = True
            with patch.dict("os.environ", {"OSTUTOR_TEST_MODE": "0"}):
                with self.assertRaises(llm.LLMError):
                    await llm.generate([{"role": "user", "content": "test"}])
        finally:
            settings.llm_base_url, settings.llm_required = old_base, old_required

    async def test_test_mode_keeps_extractive_fallback(self):
        old_base, old_required = settings.llm_base_url, settings.llm_required
        try:
            settings.llm_base_url = ""
            settings.llm_required = True
            with patch.dict("os.environ", {"OSTUTOR_TEST_MODE": "1"}):
                answer, latency = await llm.generate([{"role": "user", "content": "test"}])
            self.assertIsNone(answer)
            self.assertEqual(latency, 0.0)
        finally:
            settings.llm_base_url, settings.llm_required = old_base, old_required


if __name__ == "__main__":
    unittest.main()
