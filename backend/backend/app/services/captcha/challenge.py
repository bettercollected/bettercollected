"""The challenge and its proof: pure functions, no database, no clock of their
own (docs/captcha.md).

A challenge is ``base64url(JSON claims) "." base64url(HMAC-SHA256)``, signed
under a key derived from the JWT key ring with a purpose label of its own (the
way ``services/ai/notice_token.py`` does it: the first member signs, every
member verifies, so a key rotation drops nothing; the label makes a challenge
never a valid JWT signature and the other way round). It states, and the
signature binds: the purpose, the workspace, the form, an expiry, a random
nonce, the difficulty, whether the signed-in discount was given (``s``) and a
day-salted tag of the client's network (empty when the client is not known).

The work: find ``SUBPUZZLES`` counters ``c_i`` such that
``SHA256(challenge ":" i ":" c_i)`` starts with at least ``bits - 3`` zero bits.
Eight smaller puzzles instead of one keep the spread of the solve time small
(one puzzle is exponentially distributed, which would leave a slow phone with a
long tail); the expected work is ``2^bits`` hashes in all and checking it takes
eight. The proof travels in the ``X-BC-Captcha`` header as
``<challenge>.<c_0>,...,<c_7>``.

Nothing here logs or returns a challenge, a proof, a tag or a key.
"""

import base64
import datetime as dt
import hashlib
import hmac
import json
import re
import secrets
from dataclasses import dataclass
from typing import List, Optional, Sequence

from common.settings import key_ring

from backend.config import settings

HEADER = "X-BC-Captcha"
VERSION = 1
ALGORITHM = "sha256-lz"
SUBPUZZLES = 8
# the work is 2^bits hashes in all: 8 sub-puzzles of (bits - 3) zero bits each
SUBPUZZLE_SHIFT = 3
MIN_BITS = 14
MAX_BITS = 20
TTL = dt.timedelta(minutes=15)
# a challenge is still accepted this long after it expired (clocks, a slow request)
EXPIRY_SKEW = dt.timedelta(seconds=60)
# a spent nonce is remembered this long past the accept window: replicas'
# clocks differ, and one that runs behind still accepts a proof the others
# no longer do
CLAIM_MARGIN = dt.timedelta(minutes=5)
MAX_HEADER_LENGTH = 1024
MAX_COUNTER_DIGITS = 12
TAG_BYTES = 8
PURPOSES = ("submit",)
_PURPOSE_LABEL = b"bettercollected/captcha-challenge/v1"
_COUNTER = re.compile(r"[0-9]{1,%d}" % MAX_COUNTER_DIGITS)

INVALID = "captcha_invalid"
EXPIRED = "captcha_expired"
REPLAYED = "captcha_replayed"
MISSING = "captcha_missing"


class Refused(Exception):
    """A proof that is not accepted; ``code`` is one of the codes above."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class Claims:
    purpose: str
    workspace_id: str
    form_id: str
    bits: int
    nonce: str
    expires_ms: int
    day: int
    tag: str
    # issued at the signed-in difficulty: good only for a signed-in submit
    discounted: bool = False


def _keys() -> List[bytes]:
    """One signing key per member of the JWT key ring (current first)."""
    return key_ring.derive_all(
        key_ring.token_members(settings.auth_settings.JWT_SECRET), _PURPOSE_LABEL
    )


def available() -> bool:
    """Whether the server has a secret to sign with (it fails closed without)."""
    return bool(_keys())


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _sign(key: bytes, payload: str) -> str:
    return _b64(hmac.new(key, payload.encode("ascii"), hashlib.sha256).digest())


def _ms(value: dt.datetime) -> int:
    return int(value.timestamp() * 1000)


def _now(now: Optional[dt.datetime]) -> dt.datetime:
    return now or dt.datetime.now(dt.timezone.utc)


def day_number(now: dt.datetime) -> int:
    """The UTC day a challenge was issued on."""
    return int(now.timestamp() // 86400)


def ip_tag(key: bytes, day: int, client: str) -> str:
    """A short tag of the client's network that only the server can compute,
    under a salt that changes every UTC day by construction (derived from the
    signed day number, so nothing is stored and a challenge near midnight
    still verifies). The tag lives only inside the challenge the client holds;
    it names nobody and is empty for a client that is not known."""
    if not client:
        return ""
    salt = hmac.new(key, b"captcha-ip-salt|" + str(day).encode(), hashlib.sha256)
    tag = hmac.new(salt.digest(), client.encode("utf-8"), hashlib.sha256)
    return tag.hexdigest()[: TAG_BYTES * 2]


def issue(
    *,
    purpose: str,
    workspace_id,
    form_id,
    bits: int,
    client: str,
    discounted: bool = False,
    nonce: Optional[bytes] = None,
    now: Optional[dt.datetime] = None,
) -> Optional[str]:
    """A signed challenge, or None when the server has no secret to sign it
    with. ``client`` is the limiter's client key, or "" when it is not known.
    ``discounted``: the difficulty was lowered for a signed-in respondent; the
    proof is then good only for a submit made while signed in."""
    keys = _keys()
    if not keys:
        return None
    issued = _now(now)
    day = day_number(issued)
    claims = {
        "v": VERSION,
        "alg": ALGORITHM,
        "p": purpose,
        "w": str(workspace_id),
        "f": str(form_id),
        "n": _b64(nonce if nonce is not None else _random(16)),
        "b": int(bits),
        "k": SUBPUZZLES,
        "d": day,
        "t": ip_tag(keys[0], day, client),
        "e": _ms(issued + TTL),
    }
    if discounted:
        claims["s"] = 1
    payload = _b64(json.dumps(claims, separators=(",", ":")).encode("utf-8"))
    return f"{payload}.{_sign(keys[0], payload)}"


def _random(size: int) -> bytes:
    return secrets.token_bytes(size)


def expires_at(claims: Claims) -> dt.datetime:
    """How long a spent nonce must be remembered: until the challenge could no
    longer be accepted by any replica, whatever its clock (the accept window
    plus ``CLAIM_MARGIN``)."""
    return (
        dt.datetime.fromtimestamp(claims.expires_ms / 1000, dt.timezone.utc)
        + EXPIRY_SKEW
        + CLAIM_MARGIN
    )


def leading_zero_bits(digest: bytes) -> int:
    return len(digest) * 8 - int.from_bytes(digest, "big").bit_length()


def _hash(challenge: str, index: int, counter: str) -> bytes:
    return hashlib.sha256(f"{challenge}:{index}:{counter}".encode("ascii")).digest()


def subpuzzle_bits(bits: int) -> int:
    return bits - SUBPUZZLE_SHIFT


def solve(challenge: str) -> List[int]:
    """The counters that solve ``challenge`` (what the browser does; here for
    tests and tools: it is the same work, in Python, so slower)."""
    claims = unverified_claims(challenge)
    need = subpuzzle_bits(int(claims["b"]))
    counters = []
    for index in range(SUBPUZZLES):
        counter = 0
        while leading_zero_bits(_hash(challenge, index, str(counter))) < need:
            counter += 1
        counters.append(counter)
    return counters


def proof(challenge: str, counters: Sequence[int]) -> str:
    """The value of the ``X-BC-Captcha`` header."""
    return f"{challenge}.{','.join(str(c) for c in counters)}"


def unverified_claims(challenge: str) -> dict:
    return json.loads(_unb64(challenge.split(".")[0]))


def check(
    header: Optional[str],
    *,
    purpose: str,
    workspace_id,
    form_id,
    client: str,
    now: Optional[dt.datetime] = None,
) -> Claims:
    """The claims of ``header`` when it is a proof for this request, else
    ``Refused``. Every check but the single-use claim, cheapest first, nothing
    but memory: a flood of junk costs a signature check and a few hashes and
    never a write. ``client`` is the limiter's client key ("" when unknown)."""
    if not header or not isinstance(header, str):
        raise Refused(MISSING)
    if len(header) > MAX_HEADER_LENGTH or not header.isascii():
        raise Refused(INVALID)
    parts = header.split(".")
    if len(parts) != 3:
        raise Refused(INVALID)
    payload, signature, counters = parts
    key = _signing_key(payload, signature)
    if key is None:
        raise Refused(INVALID)
    claims = _parse(payload)
    when = _now(now)
    if _ms(when) > claims.expires_ms + int(EXPIRY_SKEW.total_seconds() * 1000):
        raise Refused(EXPIRED)
    if (
        claims.purpose != purpose
        or claims.workspace_id != str(workspace_id)
        or claims.form_id != str(form_id)
    ):
        raise Refused(INVALID)
    if claims.tag and not hmac.compare_digest(
        claims.tag, ip_tag(key, claims.day, client)
    ):
        raise Refused(INVALID)
    values = counters.split(",")
    if len(values) != SUBPUZZLES or not all(_COUNTER.fullmatch(v) for v in values):
        raise Refused(INVALID)
    need = subpuzzle_bits(claims.bits)
    solved = f"{payload}.{signature}"
    for index, value in enumerate(values):
        if leading_zero_bits(_hash(solved, index, value)) < need:
            raise Refused(INVALID)
    return claims


def _signing_key(payload: str, signature: str) -> Optional[bytes]:
    found = None
    for key in _keys():
        if hmac.compare_digest(_sign(key, payload), signature):
            found = key
    return found


def _parse(payload: str) -> Claims:
    try:
        raw = json.loads(_unb64(payload))
        if (
            not isinstance(raw, dict)
            or raw.get("v") != VERSION
            or raw.get("alg") != ALGORITHM
            or raw.get("k") != SUBPUZZLES
        ):
            raise ValueError
        bits, expires, day = raw["b"], raw["e"], raw["d"]
        for number in (bits, expires, day):
            if not isinstance(number, int) or isinstance(number, bool):
                raise ValueError
        for text in ("p", "w", "f", "n", "t"):
            if not isinstance(raw[text], str):
                raise ValueError
        discounted = raw.get("s", 0)
        if discounted not in (0, 1) or isinstance(discounted, bool):
            raise ValueError
        # the signature makes these ours; a value outside the range is a bug
        # or an old server's, never a cheaper proof
        if not MIN_BITS <= bits <= MAX_BITS:
            raise ValueError
        return Claims(
            purpose=raw["p"],
            workspace_id=raw["w"],
            form_id=raw["f"],
            bits=bits,
            nonce=raw["n"],
            expires_ms=expires,
            day=day,
            tag=raw["t"],
            discounted=discounted == 1,
        )
    except (ValueError, TypeError, KeyError, UnicodeError):
        raise Refused(INVALID)
