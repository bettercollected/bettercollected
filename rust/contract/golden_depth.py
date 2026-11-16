"""Golden vectors for the body-nesting rule (``bc-http/src/json_depth.rs``): what the
Python code itself (``backend/app/utils/json_depth.py``) answers for each body.

Run from the repository root (standard library only: no settings, database or
backend environment needed)::

    python3 -I rust/contract/golden_depth.py rust/bc-http/tests/golden/json_depth.json

Every case carries the body as a recipe (`parts`: base64 pieces and how many times each
repeats, so a body past one MiB stays small in the file) and the answer of ``too_deep`` (the whole value) and of
``DepthScanner`` fed the body in pieces of 1, 2, 3, 7 and 4096 bytes; the generator
refuses to write a file in which the two ways disagree. The constants (limit, code,
message) are read from the module, never typed here.
"""

import base64
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pyload  # noqa: E402

pyload.install()

# the module raises the application's HTTPException only in body_too_deep(), which
# the vectors do not call: a stand-in keeps the generator free of the web framework
import types  # noqa: E402

_exceptions = types.ModuleType("backend.app.exceptions")
_exceptions.HTTPException = Exception
sys.modules["backend.app.exceptions"] = _exceptions

from backend.app.utils import json_depth  # noqa: E402

LIMIT = json_depth.MAX_JSON_DEPTH


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


def pieces(body: bytes, size: int):
    return [body[i : i + size] for i in range(0, len(body), size)] or [b""]


def streamed(body: bytes, size: int) -> bool:
    scanner = json_depth.DepthScanner()
    return any(scanner.feed(piece) for piece in pieces(body, size))


def rep(piece: bytes, times: int):
    return (piece, times)


def arrays(n: int):
    return [rep(b"[", n), rep(b"]", n)]


def objects(n: int):
    return [rep(b'{"a":', n), b"1", rep(b"}", n)]


def alternating(n: int):
    """n levels, objects and arrays alternately."""
    opens = b"".join(b"[" if i % 2 else b'{"k":' for i in range(n))
    closes = b"".join(b"]" if i % 2 else b"}" for i in reversed(range(n)))
    return [opens, b"1", closes]


MIB = 1024 * 1024


def bodies() -> list:
    out = []
    for n in (1, 2, 64, 127, LIMIT - 1, LIMIT, LIMIT + 1, LIMIT + 2, 500, 982, 983, 1500, 100_000):
        out.append((f"arrays {n}", arrays(n)))
        out.append((f"objects {n}", objects(n)))
    for n in (LIMIT, LIMIT + 1):
        out.append((f"alternating {n}", alternating(n)))
        # the nesting sits inside, padding around it
        out.append((f"arrays {n} padded", [rep(b" ", 5000), *arrays(n), rep(b" ", 5000)]))
        out.append((f"arrays {n} after a long string", [b'["', rep(b"x", 5000), b'",', *arrays(n - 1), b"]"]))
    # brackets and quotes inside strings belong to the string
    out.append(("brackets in a string", [b'"', rep(b"[", 1000), b'"']))
    out.append(("brackets in a string then deep", [b'["', rep(b"[", 1000), b'",', *arrays(LIMIT), b"]"]))
    out.append(("escaped quote", [b'["\\"', rep(b"[", 1000), b'"]']))
    out.append(("escaped backslash then quote, at the limit", [b'["\\\\"', *arrays(LIMIT - 1), b"]"]))
    out.append(("escaped backslash then quote, one past the limit", [b'["\\\\"', *arrays(LIMIT), b"]"]))
    out.append(("unterminated string", [b'"', rep(b"[", 1000)]))
    out.append(("backslash at the end", [b'"abc\\']))
    out.append(("stray closers", [rep(b"]", 500), *arrays(LIMIT)]))
    out.append(("stray closers deep", [rep(b"]}", 500), *arrays(LIMIT + 1)]))
    out.append(("closed then reopened", [*arrays(LIMIT), *arrays(LIMIT), *arrays(LIMIT)]))
    out.append(("not json", [b"hello [[[ world"]))
    out.append(("empty", [b""]))
    out.append(("utf8 inside strings", ['["é\\u0022'.encode(), rep(b"[", 300), b'"]']))
    out.append(("newline in string", [b'"\n', rep(b"[", 300), b'"']))
    out.append(("past one MiB then deep", [b'{"p":"', rep(b"x", MIB + 10), b'","d":', *arrays(LIMIT + 1), b"}"]))
    out.append(("past one MiB at the limit", [b'{"p":"', rep(b"x", MIB + 10), b'","d":', *arrays(LIMIT - 1), b"}"]))
    out.append(("deep before one MiB of padding", [*arrays(LIMIT + 1), rep(b" ", MIB + 10)]))
    out.append(("one MiB of padding of strings with brackets", [b'["', rep(b"[", MIB + 10), b'"]']))
    return out


def build(parts) -> bytes:
    return b"".join(p[0] * p[1] if isinstance(p, tuple) else p for p in parts)


def main() -> None:
    out_path = Path(sys.argv[1])
    cases = []
    for name, parts in bodies():
        body = build(parts)
        whole = json_depth.too_deep(body)
        for size in (1, 2, 3, 7, 4096):
            if len(body) > 200_000 and size < 7:
                continue
            assert streamed(body, size) == whole, (name, size)
        recipe = [[b64(p[0]), p[1]] if isinstance(p, tuple) else [b64(p), 1] for p in parts]
        cases.append({"name": name, "parts": recipe, "bytes": len(body), "too_deep": whole})
    document = {
        "limit": LIMIT,
        "code": json_depth.CODE,
        "message": json_depth.MESSAGE,
        "buffered": 1024 * 1024,
        "cases": cases,
    }
    out_path.write_text(json.dumps(document, separators=(",", ":")) + "\n")
    print(f"{len(cases)} cases, {sum(c['too_deep'] for c in cases)} too deep")


main()
