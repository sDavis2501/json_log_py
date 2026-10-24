import io
import json
import logging
import unittest
from collections import OrderedDict

from json_log_py import JSONFormatter


class TestJSONFormatter(unittest.TestCase):
    def setUp(self):
        logger = logging.getLogger("json_log_py.test")
        logger.setLevel(logging.DEBUG)
        logger.handlers.clear()
        self.stream = io.StringIO()
        handler = logging.StreamHandler(self.stream)
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)
        logger.propagate = False
        self.logger = logger

    def _last(self):
        line = self.stream.getvalue().strip().splitlines()[-1]
        return json.loads(line)

    def test_basic_fields(self):
        self.logger.info("hello")
        r = self._last()
        self.assertEqual(r["msg"], "hello")
        self.assertEqual(r["level"], "INFO")
        self.assertEqual(r["logger"], "json_log_py.test")
        self.assertIn("ts", r)
        self.assertIn("line", r)
        self.assertIn("function", r)

    def test_standard_field_order(self):
        self.logger.info("order check", extra={"b": 1, "a": 2})
        r = self._last()
        keys = list(r.keys())
        self.assertEqual(
            keys[:8],
            ["ts", "level", "logger", "msg", "function", "line", "proc", "thread"],
        )

    def test_extra_fields_preserve_insertion_order(self):
        self.logger.info("extras", extra={"zeta": 1, "alpha": 2, "middle": 3})
        r = self._last()
        keys = list(r.keys())
        self.assertEqual(keys[8:], ["zeta", "alpha", "middle"])

    def test_extra_fields_ordered_dict(self):
        od = OrderedDict()
        od["second"] = 2
        od["first"] = 1
        self.logger.info("od", extra=od)
        r = self._last()
        keys = list(r.keys())
        self.assertEqual(keys[8:], ["second", "first"])

    def test_message_with_args(self):
        self.logger.info("value=%s count=%d", "ok", 42)
        r = self._last()
        self.assertEqual(r["msg"], "value=ok count=42")

    def test_exception_info(self):
        try:
            raise ValueError("boom")
        except ValueError:
            self.logger.exception("failed")
        r = self._last()
        self.assertEqual(r["exception"]["type"], "ValueError")
        self.assertEqual(r["exception"]["message"], "boom")
        self.assertIn("Traceback", r["exception"]["traceback"])
        self.assertEqual(
            list(r.keys())[-1],
            "exception",
            "exception should be the final key",
        )

    def test_exception_block_keys_after_standard(self):
        try:
            raise KeyError("missing")
        except KeyError:
            self.logger.exception("failed", extra={"req_id": "abc"})
        r = self._last()
        keys = list(r.keys())
        self.assertEqual(keys[8], "req_id")
        self.assertEqual(keys[9], "exception")

    def test_single_line_output(self):
        self.logger.info("single")
        lines = self.stream.getvalue().strip().splitlines()
        self.assertEqual(len(lines), 1)

    def test_rename_standard_key(self):
        logger = logging.getLogger("json_log_py.rename")
        logger.setLevel(logging.INFO)
        logger.handlers.clear()
        stream = io.StringIO()
        h = logging.StreamHandler(stream)
        h.setFormatter(JSONFormatter(fmt={"msg": "message"}))
        logger.addHandler(h)
        logger.propagate = False
        logger.info("hi")
        r = json.loads(stream.getvalue().strip())
        self.assertNotIn("msg", r)
        self.assertEqual(r["message"], "hi")
        self.assertEqual(
            list(r.keys())[:8],
            ["ts", "level", "logger", "message", "function", "line", "proc", "thread"],
        )

    def test_rename_non_standard_rejected(self):
        with self.assertRaises(ValueError):
            JSONFormatter(fmt={"nonexistent": "x"})

    def test_rename_collision_rejected(self):
        with self.assertRaises(ValueError):
            JSONFormatter(fmt={"msg": "level"})

    def test_datefmt_custom(self):
        logger = logging.getLogger("json_log_py.datefmt")
        logger.setLevel(logging.INFO)
        logger.handlers.clear()
        stream = io.StringIO()
        h = logging.StreamHandler(stream)
        h.setFormatter(JSONFormatter(datefmt="%Y"))
        logger.addHandler(h)
        logger.propagate = False
        logger.info("x")
        r = json.loads(stream.getvalue().strip())
        self.assertRegex(r["ts"], r"^\d{4}$")

    def test_default_timestamp_is_iso_with_millis(self):
        self.logger.info("ts")
        r = self._last()
        self.assertRegex(r["ts"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}$")

    def test_set_serialized_via_default(self):
        self.logger.info("set", extra={"items": {3, 1, 2}})
        r = self._last()
        self.assertEqual(r["items"], [1, 2, 3])

    def test_bytes_serialized_via_default(self):
        self.logger.info("bytes", extra={"raw": b"abc"})
        r = self._last()
        self.assertEqual(r["raw"], "abc")

    def test_unknown_object_falls_back_to_repr(self):
        class Weird:
            def __repr__(self):
                return "<Weird>"
        self.logger.info("obj", extra={"o": Weird()})
        r = self._last()
        self.assertEqual(r["o"], "<Weird>")

    def test_ensure_ascii_default_escapes_unicode(self):
        self.logger.info("emoji", extra={"emoji": "\u2603"})
        raw = self.stream.getvalue().strip()
        self.assertIn("\\u2603", raw)
        r = json.loads(raw)
        self.assertEqual(r["emoji"], "\u2603")

    def test_ensure_ascii_false_passes_through(self):
        logger = logging.getLogger("json_log_py.noascii")
        logger.setLevel(logging.INFO)
        logger.handlers.clear()
        stream = io.StringIO()
        h = logging.StreamHandler(stream)
        h.setFormatter(JSONFormatter(ensure_ascii=False))
        logger.addHandler(h)
        logger.propagate = False
        logger.info("snowman", extra={"emoji": "\u2603"})
        raw = stream.getvalue().strip()
        self.assertIn("\u2603", raw)

    def test_reserved_keys_not_in_extras(self):
        self.logger.info("reserved")
        r = self._last()
        for reserved in ("name", "levelname", "levelno", "pathname", "filename",
                         "module", "exc_info", "exc_text", "stack_info", "lineno",
                         "funcName", "created", "msecs", "relativeCreated",
                         "threadName", "processName", "process", "message",
                         "asctime", "args", "taskName"):
            self.assertNotIn(reserved, r, f"{reserved} leaked into output")


if __name__ == "__main__":
    unittest.main()
