from __future__ import annotations

import json
import logging
import sys
from typing import Any, Callable, Dict, Mapping, Tuple


class JSONFormatter(logging.Formatter):
    """A logging ``Formatter`` that emits each record as a single JSON line.

    Field ordering is stable: the ``standard`` keys are emitted first in a
    fixed sequence, then ``extra`` keys are emitted in the order they were
    inserted into ``record.__dict__`` (insertion order is preserved by the
    interpreter). This is the reason to use this formatter instead of the
    stdlib ``json.dumps(sort_keys=True)`` — sorted keys are stable but put
    ``message`` next to ``name``, which is unreadable. Fixed first, extras
    second is the readability trade-off we chose.

    Parameters
    ----------
    fmt:
        Maps ``msg`` to a different standard key. For example,
        ``fmt={'msg': 'message'}`` renames the ``msg`` key to ``message``.
        Renamed keys must land in the standard block, which is why this is
        a renaming map rather than free-form ``str.format``-style keys.
    datefmt:
        Passed through to ``time.strftime`` for ``asctime``. If ``None``,
        ISO-8601 with milliseconds is used.
    json_default:
        Function used by ``json.dumps`` to coerce non-JSON-native values
        (``set``, ``datetime``, custom objects). The default handles the
        common stdlib containers; pass your own to cover domain types.
    ensure_ascii:
        Forwarded to ``json.dumps``. ``True`` by default for logging —
        logs are frequently filtered by tools that assume ASCII, and
        ``ensure_ascii=False`` produces human-readable but fragile output.
    """

    _standard_keys: Tuple[str, ...] = (
        "ts",
        "level",
        "logger",
        "msg",
        "function",
        "line",
        "proc",
        "thread",
    )

    _reserved_record_keys: Tuple[str, ...] = (
        "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
        "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
        "created", "msecs", "relativeCreated", "thread", "threadName",
        "processName", "process", "message", "asctime", "taskName",
    )

    _datefmt_default: str = "%Y-%m-%dT%H:%M:%S"

    def __init__(
        self,
        *,
        fmt: Mapping[str, str] | None = None,
        datefmt: str | None = None,
        json_default: Callable[[Any], Any] | None = None,
        ensure_ascii: bool = True,
    ) -> None:
        super().__init__(datefmt=datefmt)
        self._rename: Dict[str, str] = dict(fmt) if fmt else {}
        for original, renamed in self._rename.items():
            if original not in self._standard_keys:
                raise ValueError(
                    f"fmt key {original!r} is not a standard key; "
                    "only standard keys can be renamed"
                )
            if renamed in self._standard_keys:
                raise ValueError(
                    f"rename target {renamed!r} collides with a standard key"
                )
        self._json_default = json_default or _default_json_default
        self._ensure_ascii = ensure_ascii

    def format(self, record: logging.LogRecord) -> str:
        standard: Dict[str, Any] = {}
        extras: Dict[str, Any] = {}

        asctime = self.formatTime(record, self.datefmt)
        standard_raw = {
            "ts": asctime,
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "function": record.funcName,
            "line": record.lineno,
            "proc": record.process,
            "thread": record.thread,
        }

        for original in self._standard_keys:
            target = self._rename.get(original, original)
            standard[target] = standard_raw[original]

        for key, value in record.__dict__.items():
            if key in self._reserved_record_keys:
                continue
            extras[key] = value

        ordered: Dict[str, Any] = {}
        ordered.update(standard)
        ordered.update(extras)

        if record.exc_info:
            ordered["exception"] = self._format_exception(record)

        return json.dumps(
            ordered,
            default=self._json_default,
            ensure_ascii=self._ensure_ascii,
        )

    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        # Apply the custom datefmt or fall back to ISO-8601 with milliseconds.
        # We do NOT use the base class's default because it appends a bare
        # comma-separated millis field (",123") which is not ISO-8601.
        if datefmt is None:
            base = record.__dict__.get("asctime_iso")
            if isinstance(base, str):
                return base
            import time
            t = time.localtime(record.created)
            return time.strftime(self._datefmt_default, t) + f".{int(record.msecs):03d}"
        return super().formatTime(record, datefmt)

    @staticmethod
    def _format_exception(record: logging.LogRecord) -> Dict[str, str]:
        import traceback
        exc_type, exc_value, exc_tb = record.exc_info
        if exc_type is None:
            return {"type": "", "message": "", "traceback": ""}
        tb_text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        return {
            "type": exc_type.__name__,
            "message": str(exc_value),
            "traceback": tb_text,
        }


def _default_json_default(obj: Any) -> Any:
    if isinstance(obj, set):
        return sorted(obj)
    if isinstance(obj, frozenset):
        return sorted(obj)
    if isinstance(obj, (bytes, bytearray)):
        return obj.decode("utf-8", errors="replace")
    if isinstance(obj, complex):
        return {"real": obj.real, "imag": obj.imag}
    # Fall back to repr so a custom object never silently crashes log emission.
    return repr(obj)
