"""backend/.test_durations is committed (CI splits the suite with it), and it
holds every test id. A parametrized test whose id embeds its value would put
that value in the repository: give such tests ``ids=`` that name the case.
This keeps key-shaped strings out of the file, so the file never looks like a
leak to a reader or a secret scanner (and random ids would not match the next
run anyway)."""

import json
import math
import re
from collections import Counter
from pathlib import Path

DURATIONS = Path(__file__).resolve().parents[1] / ".test_durations"

# well-known secret formats, by prefix or framing
KNOWN = re.compile(
    r"(?<![A-Za-z0-9])("
    r"sk-|sk_live_|sk_test_|rk_live_|pk_live_|AKIA[0-9A-Z]{8}|ASIA[0-9A-Z]{8}|AIza[0-9A-Za-z_-]{8}"
    r"|GOCSPX-|gh[pousr]_|github_pat_|glpat-|xox[abprs]-|whsec_|hf_[A-Za-z]{8}|npm_[A-Za-z0-9]{8}"
    r"|eyJ[A-Za-z0-9_-]{8}"
    r")|-----BEGIN|PRIVATE KEY"
)
TOKEN = re.compile(r"[A-Za-z0-9+/_=-]{20,}")


def _entropy(text: str) -> float:
    counts = Counter(text)
    return -sum(n / len(text) * math.log2(n / len(text)) for n in counts.values())


def _random_looking(token: str) -> bool:
    """Base64 or hex noise, as opposed to words, names and paths."""
    # base64-like: a stretch without separators that mixes upper, lower and
    # digits throughout (names, paths and setting keys are words between
    # - _ . /)
    for part in re.split(r"[-_./]", token):
        if (
            len(part) >= 16
            and re.search(r"[a-z]", part)
            and re.search(r"[A-Z]", part)
            and sum(c.isdigit() for c in part) >= 2
            and _entropy(part) >= 3.5
        ):
            return True
    # hex-like: a long run of hex digits with letters and digits mixed
    for run in re.findall(r"[0-9a-fA-F]{24,}", token):
        if re.search(r"[a-fA-F]", run) and re.search(r"[0-9]", run) and _entropy(run) >= 3.0:
            return True
    return False


def secret_like(test_id: str) -> list:
    """The parts of a test id that look like a key, a token or a credential."""
    params = test_id[test_id.find("[") :] if "[" in test_id else ""
    found = [m.group(0) for m in KNOWN.finditer(params)]
    for token in TOKEN.findall(params):
        if _random_looking(token):
            found.append(token)
    return found


def test_the_detector_catches_key_shaped_ids():
    assert secret_like("t.py::test[sk-abcdefghijklmnop]")
    assert secret_like("t.py::test[AKIAABCDEFGHIJKLMNOP]")
    assert secret_like("t.py::test[eyJhbGciOiJIUzI1NiJ9.e30.x]")
    assert secret_like("t.py::test[9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08]")
    assert secret_like("t.py::test[q8Xr2LmZ0pW4tYv7Nc1Ks9Bd]")


def test_the_detector_leaves_ordinary_ids_alone():
    for fine in (
        "t.py::test[openai-0]",
        "t.py::test[random-hex-17]",
        "t.py::test[task-runner]",
        "t.py::test[AIPreferenceMemoryRepository-PostgresAIPreferenceMemoryRepository]",
        "t.py::test[https://images.unsplash.com/photo-1500530855697-b586d89ba3ee]",
        "t.py::test[" + "a" * 64 + "]",
        "t.py::test[after-2026-03-12-2026-03-12-True]",
    ):
        assert not secret_like(fine), fine


def test_no_recorded_test_id_looks_like_a_secret():
    ids = json.loads(DURATIONS.read_text())
    offenders = {test_id.split("[")[0] for test_id in ids if secret_like(test_id)}
    assert not offenders, (
        "test ids that embed key-shaped values (give the parametrize ids= that "
        f"name the case): {sorted(offenders)}"
    )
