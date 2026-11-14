"""Issuing and checking the proof of work (docs/captcha.md).

``CaptchaService.issue`` signs a challenge whose difficulty is the base for the
purpose plus the pressure this process has seen, less three bits for a
signed-in respondent (floor 14, never above 20; the signed challenge says so
and a proof issued at that difficulty is accepted only on a signed-in submit). ``CaptchaService.require``
checks a proof: every check that needs only memory comes first
(``challenge.check``), and the one write, the single-use claim of the nonce
through ``FixedWindowRateLimiter.claim``, comes last, so a flood of junk
costs a signature check and a few hashes and never a database write.

The challenge is bound to a day-salted tag of the client's network. The client
is the one the respondent limits count (``respondent_limits.client_key``): a
client the API cannot tell (a proxy not in TRUSTED_PROXIES makes every user
one client) gets an empty tag, is not counted for pressure and is not limited
on the challenge route, exactly as with the submit limit.

Logged: outcome codes only (counts by outcome), never a challenge, a proof, a
tag or an address.
"""

import hashlib
import math
import time
from http import HTTPStatus
from typing import Callable, Optional, Tuple

from loguru import logger

from backend.app.exceptions import HTTPException
from backend.app.services.captcha import challenge
from backend.app.services.captcha.challenge import Refused
from backend.app.services.captcha.pressure import Pressure
from backend.app.services.captcha.stats import CaptchaStats
from backend.app.services.rate_limiter import FixedWindowRateLimiter, Verdict
from backend.app.services.respondent_limits import client_key, too_many
from backend.config import (
    settings,
)  # noqa: F401  (builds the settings and the live() groups)
from common.settings.loader import live

CLAIM_SCOPE = "captcha-nonce"
UNKNOWN = "unknown"
# many people behind one address (an office, a school): this many challenges in
# ten minutes are free
FREE_ISSUES = 30
MAX_ISSUE_PRESSURE = 2
FAILURES_FOR_PRESSURE = 3
FAILURE_PRESSURE = 2
# submits per minute on one form (this process) that add a bit, and two
FORM_BUSY = 30
FORM_VERY_BUSY = 120
MAX_PRESSURE = 4
SIGNED_IN_DISCOUNT = 3
# challenge requests per minute per client and purpose
CHALLENGES_PER_MINUTE = 300

_MESSAGES = {
    challenge.MISSING: "The automatic spam check is missing from this request.",
    challenge.INVALID: "The automatic spam check did not pass.",
    challenge.EXPIRED: "The automatic spam check has expired.",
    challenge.REPLAYED: "The automatic spam check was already used.",
}


def refusal(code: str) -> HTTPException:
    """422 with the code the form page reacts to (it asks for a new proof and
    sends again, once, for any of these)."""
    return HTTPException(
        status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        content={"code": code, "message": _MESSAGES[code]},
    )


def _tag_client(client: Optional[str]) -> str:
    """The limiter's client key, or "" when the client is not known."""
    key = client_key(client)
    return "" if key == UNKNOWN else key


class CaptchaService:
    def __init__(
        self,
        rate_limiter: FixedWindowRateLimiter,
        pressure: Optional[Pressure] = None,
        clock: Callable[[], float] = time.time,
        stats: Optional[CaptchaStats] = None,
    ):
        self._limiter = rate_limiter
        self.pressure = pressure or Pressure(clock)
        # daily counts by outcome (stats.py); without it only the log line is written
        self.stats = stats

    # -- difficulty

    def difficulty(
        self,
        client: str,
        form_id: str,
        signed_in: bool,
        count: bool = True,
        purpose: str = "submit",
    ) -> int:
        """The bits to ask of this client now. ``client`` is "" when unknown
        (no per-client pressure then). ``count`` registers this issue."""
        return self._difficulty(client, form_id, signed_in, count, purpose)[0]

    def _difficulty(
        self,
        client: str,
        form_id: str,
        signed_in: bool,
        count: bool = True,
        purpose: str = "submit",
    ) -> Tuple[int, bool]:
        """``(bits, whether the signed-in discount lowered them)``. The base is
        the purpose's (a mail costs the instance its reputation, so its base is
        a bit higher); the form's submit rate and the signed-in discount are the
        submit's alone (a sign-in code is asked for by someone who is not signed
        in, a draft link only by an anonymous respondent)."""
        api = live().api
        submit = purpose == "submit"
        base = int(api.CAPTCHA_BASE_BITS_SUBMIT if submit else api.CAPTCHA_BASE_BITS_MAIL)
        extra = int(api.CAPTCHA_DIFFICULTY_BOOST)
        if client:
            issued = self.pressure.issued(client) if count else 0
            if issued > FREE_ISSUES:
                extra += min(
                    MAX_ISSUE_PRESSURE, math.ceil(math.log2(issued / FREE_ISSUES))
                )
            if self.pressure.failures(client) >= FAILURES_FOR_PRESSURE:
                extra += FAILURE_PRESSURE
        busy = self.pressure.submits_last_minute(form_id) if submit else 0
        if busy > FORM_VERY_BUSY:
            extra += 2
        elif busy > FORM_BUSY:
            extra += 1
        bits = min(
            challenge.MAX_BITS,
            base + min(extra, MAX_PRESSURE),
        )
        full = max(challenge.MIN_BITS, min(challenge.MAX_BITS, bits))
        if not signed_in or not submit:
            return full, False
        lowered = max(
            challenge.MIN_BITS, min(challenge.MAX_BITS, bits - SIGNED_IN_DISCOUNT)
        )
        return lowered, lowered < full

    # -- the challenge route

    def allow_request(self, client: Optional[str], purpose: str) -> None:
        """The challenge route's coarse limit (memory): 429 with Retry-After
        past ``CHALLENGES_PER_MINUTE`` a minute per client and purpose. No
        limit for a client that is not known."""
        tag = _tag_client(client)
        if not tag:
            return
        allowed, wait = self.pressure.ask(tag, purpose, CHALLENGES_PER_MINUTE)
        if not allowed:
            # counted for no workspace or form: the request is not looked at yet
            # (a flood must not become a flood of distinct keys)
            self._outcome("rate_limited", purpose)
            raise too_many(Verdict(allowed=False, count=0, retry_after=wait))

    def issue(
        self,
        *,
        purpose: str,
        workspace_id,
        form_id,
        client: Optional[str],
        signed_in: bool,
    ) -> Optional[dict]:
        """A challenge for the response body, or None when the server cannot
        sign (no secret)."""
        tag = _tag_client(client)
        bits, discounted = self._difficulty(
            tag, str(form_id), signed_in, purpose=purpose
        )
        text = challenge.issue(
            purpose=purpose,
            workspace_id=workspace_id,
            form_id=form_id,
            bits=bits,
            client=tag,
            discounted=discounted,
        )
        if text is None:
            return None
        self._outcome("issued", purpose, workspace_id, form_id)
        claims = challenge.unverified_claims(text)
        return {
            "challenge": text,
            "algorithm": challenge.ALGORITHM,
            "bits": bits,
            "subpuzzles": challenge.SUBPUZZLES,
            "expiresAt": claims["e"],
        }

    # -- checking a proof

    async def require(
        self,
        header: Optional[str],
        *,
        purpose: str,
        workspace_id,
        form_id,
        client: Optional[str],
        signed_in: bool = False,
    ) -> None:
        """Pass when ``header`` is a valid, unspent proof for this request;
        else raise 422 with ``captcha_missing`` / ``captcha_invalid`` /
        ``captcha_expired`` / ``captcha_replayed``. Nothing was stored for a
        request refused here. A proof issued at the signed-in difficulty
        (claim ``s``) is refused as ``captcha_invalid``, before its nonce is
        claimed, unless ``signed_in``: the discount is for the submit it was
        given for, not for an anonymous one."""
        tag = _tag_client(client)
        try:
            claims = challenge.check(
                header,
                purpose=purpose,
                workspace_id=workspace_id,
                form_id=form_id,
                client=tag,
            )
        except Refused as refused:
            self._outcome(refused.code, purpose, workspace_id, form_id)
            if refused.code == challenge.INVALID and tag:
                self.pressure.failed(tag)
            raise refusal(refused.code)
        if claims.discounted and not signed_in:
            self._outcome(challenge.INVALID, purpose, workspace_id, form_id)
            if tag:
                self.pressure.failed(tag)
            raise refusal(challenge.INVALID)
        spent = hashlib.sha256(claims.nonce.encode("ascii", "ignore")).hexdigest()
        # the one write, last: the first caller of a nonce wins, on any replica
        if not await self._limiter.claim(
            CLAIM_SCOPE, spent, challenge.expires_at(claims)
        ):
            self._outcome(challenge.REPLAYED, purpose, workspace_id, form_id)
            if tag:
                self.pressure.failed(tag)
            raise refusal(challenge.REPLAYED)
        self._outcome("verified", purpose, workspace_id, form_id)

    def note_submit(self, form_id) -> None:
        """A response to ``form_id`` was stored: the form's own submit rate,
        which raises the difficulty of the next challenges while it is high."""
        self.pressure.submitted(str(form_id))

    def _outcome(
        self, outcome: str, purpose: str, workspace_id="", form_id=""
    ) -> None:
        """Log the outcome (code and purpose only) and count it for the day
        (``stats.py``: in memory, written later)."""
        logger.info("captcha outcome={} purpose={}", outcome, purpose)
        if self.stats is not None:
            self.stats.record(outcome, purpose, workspace_id, form_id)
