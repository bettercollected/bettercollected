"""Rate limits of the two respondent-facing routes that had none of their own:
the sign-in code mail (``POST /workspaces/{id}/auth/otp/send`` and
``POST /auth/creator/otp/send``) and the response submit
(``POST /workspaces/{id}/forms/{id}/response``).

Fixed windows counted in the database (``FixedWindowRateLimiter``, shared by
every replica); every counter id is a keyed hash, so no address and no client
is stored. The numbers are constants, like the draft-link limits
(``services/form_drafts/limits.py``).

Sign-in code mail (a mail bomb of any address is the abuse):

* per client: 10 an hour (``rate_limit_key``: an IPv6 client by its /64);
* per address: 3 an hour, whichever route or workspace asked. The address is
  folded first (Unicode NFC, case, internationalised domain, and a ``+tag`` of
  the local part), so ``a+1@x`` and ``A+2@x`` are the one mailbox;
* per workspace (the creator sign-in counts as one more scope): 1000 an hour;
* for the whole instance: 5000 an hour.

Every request counts, found address or not: the limits are checked before the
auth service is asked anything, so a refusal never differs by whether the
address has an account (or is covered by single sign-on elsewhere). A client
the API cannot tell ("unknown": no trusted proxy configured, or an address
that does not parse) is not limited per client: every such request shares one
bucket, so that limit would lock everyone out together. The address, workspace
and instance limits still hold for it.

Submit (a flood of responses is the abuse; real busy forms must not notice):

* per client and form: 120 a minute (a venue's wifi is one address);
* per form: 1000 a minute. One form cannot be used to drown the others, and a
  limit this high cannot be reached by honest traffic of one form (the form's
  own response limit and retention rules are separate).

The same "unknown" rule applies: only the per-form limit holds then.

Not covered here on purpose: the Submissions API (a key, its own limits in
``public_api/auth.py``) calls the submit service directly and never passes
through the respondent route.

A refusal is 429 ``{"code": "rate_limited", "message": ...}`` with
``Retry-After`` (seconds to the end of the window). Nothing here logs an address
or a client.
"""

import unicodedata
from http import HTTPStatus
from typing import Optional

from loguru import logger

from backend.app.exceptions import HTTPException
from backend.app.services.rate_limiter import FixedWindowRateLimiter, Verdict
from backend.app.utils.client_ip import rate_limit_key

HOUR = 3600
MINUTE = 60

# as (scope, limit, window seconds)
CODE_PER_CLIENT = ("code-mail-client", 10, HOUR)
CODE_PER_ADDRESS = ("code-mail-address", 3, HOUR)
CODE_PER_WORKSPACE = ("code-mail-workspace", 1000, HOUR)
# the creator sign-in has no workspace: it is one scope of its own
CODE_CREATOR = ("code-mail-creator", 1000, HOUR)
CODE_ALL = ("code-mail-all", 5000, HOUR)

SUBMIT_PER_CLIENT_FORM = ("submit-client-form", 120, MINUTE)
SUBMIT_PER_FORM = ("submit-form", 1000, MINUTE)

_ALL = "*"
_UNKNOWN = "unknown"

RATE_LIMITED = "rate_limited"
MESSAGES = {
    "en": "Too many attempts. Please try again in {wait}.",
    "nl": "Te veel pogingen. Probeer het over {wait} opnieuw.",
}


def _wait(seconds: int, lang: str) -> str:
    minutes = -(-seconds // 60)
    if minutes <= 1:
        return "een minuut" if lang == "nl" else "a minute"
    if minutes >= 120:
        hours = -(-minutes // 60)
        return f"{hours} uur" if lang == "nl" else f"{hours} hours"
    return f"{minutes} minuten" if lang == "nl" else f"{minutes} minutes"


def _language(locale: Optional[str]) -> str:
    return "nl" if (locale or "").strip().lower().startswith("nl") else "en"


def too_many(verdict: Verdict, locale: Optional[str] = None) -> HTTPException:
    lang = _language(locale)
    return HTTPException(
        status_code=HTTPStatus.TOO_MANY_REQUESTS,
        content={
            "code": RATE_LIMITED,
            "message": MESSAGES[lang].format(wait=_wait(verdict.retry_after, lang)),
            "retry_after": verdict.retry_after,
        },
        headers={"Retry-After": str(verdict.retry_after)},
    )


def address_limit_key(address: str) -> str:
    """The mailbox ``address`` stands for, as far as a limit can tell: Unicode
    NFC, case folded, the domain in its ASCII form, and a ``+tag`` of the local
    part dropped (it reaches the same mailbox). Dots are left alone: whether
    they matter depends on the provider."""
    text = unicodedata.normalize("NFC", (address or "").strip())
    local, at, domain = text.rpartition("@")
    if not at:
        return text.casefold()
    local = local.casefold()
    local = local.split("+", 1)[0] or local
    try:
        domain = domain.encode("idna").decode("ascii")
    except UnicodeError:
        pass
    return f"{local}@{domain.casefold()}"


class RespondentLimits:
    def __init__(self, rate_limiter: FixedWindowRateLimiter):
        self._limiter = rate_limiter

    async def _hit(self, spec, key: str, locale: Optional[str] = None) -> None:
        scope, limit, window = spec
        verdict = await self._limiter.hit(scope, key, limit, window)
        if not verdict.allowed:
            logger.info("Request refused: too many requests ({})", scope)
            raise too_many(verdict, locale)

    async def code_mail(
        self,
        client: Optional[str],
        address: str,
        workspace_id: Optional[str] = None,
        locale: Optional[str] = None,
    ) -> None:
        """Count one request for a sign-in code mail to ``address`` (raises 429
        when a limit is used up). Call it before anything is looked up about
        the address. ``workspace_id`` is None for the creator sign-in."""
        key = rate_limit_key(client)
        # the cheapest refusal first; a request refused by one limit does not
        # use up the budgets after it
        if key != _UNKNOWN:
            await self._hit(CODE_PER_CLIENT, key, locale)
        await self._hit(CODE_PER_ADDRESS, address_limit_key(address), locale)
        if workspace_id is None:
            await self._hit(CODE_CREATOR, _ALL, locale)
        else:
            await self._hit(CODE_PER_WORKSPACE, str(workspace_id), locale)
        await self._hit(CODE_ALL, _ALL, locale)

    async def submit(
        self, client: Optional[str], workspace_id: str, form_id: str
    ) -> None:
        """Count one response submit to a form (raises 429 when a limit is used
        up). Call it before the body is read further."""
        key = rate_limit_key(client)
        form = f"{workspace_id}:{form_id}"
        if key != _UNKNOWN:
            await self._hit(SUBMIT_PER_CLIENT_FORM, f"{key}\n{form}")
        await self._hit(SUBMIT_PER_FORM, form)
