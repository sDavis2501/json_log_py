# json_log_py

A structured logging `Formatter` for the standard library `logging` module that emits each record as a single line of JSON with stable, readable field ordering.

```python
import logging
from json_log_py import JSONFormatter

handler = logging.StreamHandler()
handler.setFormatter(JSONFormatter())

logger = logging.getLogger("myapp")
logger.addHandler(handler)
logger.setLevel(logging.INFO)

logger.info("started", extra={"request_id": "abc-123"})
# {"ts":"2024-05-01T10:00:00.000","level":"INFO","logger":"myapp","msg":"started","function":"<module>","line":1,"proc":12345,"thread":12345,"request_id":"abc-123"}
```

## Why

Plain text logs are easy to read but hard to query. JSON logs are easy to query but unreadable in a terminal. The middle ground most JSON loggers pick is `json.dumps(sort_keys=True)`, which is stable but puts `message` next to `logger` and shuffles extras alphabetically. This formatter keeps the standard fields (`ts`, `level`, `logger`, `msg`, `function`, `line`, `proc`, `thread`) in a fixed, readable order at the front, then appends user-supplied extras in insertion order. Extras use insertion order rather than alphabetical so that `extra={'step': 3, 'phase': 'build'}` appears in the order you wrote it — useful when scanning a pipeline log.

Renaming a standard key (e.g. `msg` → `message`) is supported via `fmt`, but only for standard keys; extras are emitted under the names the caller passed. The `exc_info` block, when present, is always the final key so multi-line tracebacks sit at the end of the line.

## Edge cases

- Non-JSON-native values in extras (sets, bytes, custom objects) are coerced via `json.dumps`'s `default` callback. The built-in default handles `set`/`frozenset` (sorted list), `bytes`/`bytearray` (UTF-8 decoded with replacement), and `complex`; anything else falls back to `repr(obj)` so log emission never crashes. Pass `json_default=` to override.
- Timestamps default to ISO-8601 with millisecond precision (`2024-05-01T10:00:00.123`). Pass `datefmt=` for `strftime` formatting; note the stdlib default appends bare `,123` millis which is not ISO, so this formatter overrides it.
- `ensure_ascii` defaults to `True` (escaped Unicode). This is safer for log pipelines that assume ASCII. Set it to `False` for human-readable UTF-8 in development.

## Performance

The window keeps a bounded buffer, so `push` is constant time and memory does not
grow with the length of the stream. `peak` and `trough` are linear in the window
size, which is the trade that keeps `push` cheap.

