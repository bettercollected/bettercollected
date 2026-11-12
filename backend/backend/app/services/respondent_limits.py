"""Rate limits of the two respondent-facing routes that had none of their own:
the sign-in code mail (``POST /workspaces/{id}/auth/otp/send`` and
``POST /auth/creator/otp/send``) and the response submit
(``POST /workspaces/{id}/forms/{id}/response``).

Fixed windows counted in the database (``FixedWindowRateLimiter``, shared by
every replica); every counter id is a keyed hash, so no address and no client
is stored.

Design rule: a budget that many people share (a workspace, a form, all
creators) is a lever for denial of service, because anyone with a few
networks can use it up for everybody. So the budgets here are per person
(per client network, per mailbox) and there is exactly one shared budget, the
code-mail circuit breaker below.

Sign-in code mail (a mail bomb of any address, or the code mail used as a
relay to random addresses, is the abuse):

* per client: 10 an hour. The client is its trusted-proxy address (see
  ``utils/client_ip.limit_client_ip``), an IPv6 client by its /48 (one site's
  allocation, so a /64 per device does not multiply the limit);
* per address: 3 an hour, whichever route or workspace asked. The address is
  folded first (Unicode NFC, case, an internationalised domain, a ``+tag`` of
  the local part, and for Gmail the dots, ``googlemail.com`` being
  ``gmail.com``), so spellings of one mailbox share the budget;
* for the whole instance: ``API_CODE_MAIL_PER_HOUR`` (default 20000, 0 turns
  it off), the circuit breaker. It is the only brake on the code mail being
  used to mail random addresses, so it sits far above normal use, and it is
  logged at ERROR the moment it trips so an operator sees an attack instead
  of users silently losing sign-in. It is a stop-gap until a proof of work is
  asked for on these routes; the proof of work replaces it.

Every request counts, found address or not: the limits are checked before the
auth service is asked anything, so a refusal never differs by whether the
address has an account (or is covered by single sign-on elsewhere). A request
for a workspace that does not exist is not counted: it mails nothing and
answers as before.

Known trade-off (accepted until the proof of work): someone who knows an
address can keep it at its 3 an hour and so delay that person's sign-in code
for the hour. The code that was already mailed stays valid for its own
lifetime.

Submit (a flood of responses is the abuse): 30 a minute per client and form.
There is no per-form budget: a budget the form's visitors share would let a
few clients block everyone from a public form.

A client the API cannot tell ("unknown": an unparseable peer, or a proxy on a
private address that is not in TRUSTED_PROXIES and would make every user one
client) is not limited per client; the instance budget (code mail) still holds
and the submit has nothing left to count. Setting TRUSTED_PROXIES is what
turns the per-client limits on behind a proxy.

Not covered here on purpose: the Submissions API (a key, its own limits in
``public_api/auth.py``) calls the submit service directly and never passes
through the respondent route.

A refusal is 429 ``{"code": "rate_limited", "message": ..., "retry_after": s}``
with ``Retry-After`` (seconds to the end of the window). Nothing here logs an
address or a client.
"""

import ipaddress
import unicodedata
from http import HTTPStatus
from typing import Optional

from loguru import logger

from backend.app.exceptions import HTTPException
from backend.app.services.rate_limiter import FixedWindowRateLimiter, Verdict
from backend.config import settings  # noqa: F401  (builds the settings and the live() groups)
from common.settings.loader import live
from common.utils.client_ip import parse_address

HOUR = 3600
MINUTE = 60

# as (scope, limit, window seconds)
CODE_PER_CLIENT = ("code-mail-client", 10, HOUR)
CODE_PER_ADDRESS = ("code-mail-address", 3, HOUR)
# the circuit breaker's own counter; its limit is the live setting
CODE_ALL_SCOPE = "code-mail-all"
SUBMIT_PER_CLIENT_FORM = ("submit-client-form", 30, MINUTE)

_ALL = "*"
_UNKNOWN = "unknown"
GMAIL_DOMAINS = frozenset({"gmail.com", "googlemail.com"})

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


def too_many_body(verdict: Verdict, locale: Optional[str] = None) -> dict:
    lang = _language(locale)
    return {
        "code": RATE_LIMITED,
        "message": MESSAGES[lang].format(wait=_wait(verdict.retry_after, lang)),
        "retry_after": verdict.retry_after,
    }


def too_many(verdict: Verdict, locale: Optional[str] = None) -> HTTPException:
    return HTTPException(
        status_code=HTTPStatus.TOO_MANY_REQUESTS,
        content=too_many_body(verdict, locale),
        headers={"Retry-After": str(verdict.retry_after)},
    )


def client_key(client: Optional[str]) -> str:
    """The key a client address is counted under on these routes: an IPv4
    address as is, an IPv6 address by its /48; "unknown" when there is none."""
    address = parse_address(client)
    if address is None:
        return _UNKNOWN
    if address.version == 6:
        return str(ipaddress.ip_network(f"{address}/48", strict=False))
    return str(address)


def address_limit_key(address: str) -> str:
    """The mailbox ``address`` stands for, as far as a limit can tell: Unicode
    NFC, case folded, the domain in its ASCII form, a ``+tag`` of the local part
    dropped (it reaches the same mailbox) and, for Gmail (``googlemail.com`` is
    the same service), the dots of the local part dropped too. For other
    providers dots are left alone: whether they matter is theirs to say."""
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
    domain = domain.casefold()
    if domain in GMAIL_DOMAINS:
        domain = "gmail.com"
        local = local.replace(".", "") or local
    return f"{local}@{domain}"


class RespondentLimits:
    def __init__(self, rate_limiter: FixedWindowRateLimiter):
        self._limiter = rate_limiter

    async def _hit(self, spec, key: str, locale: Optional[str] = None) -> None:
        scope, limit, window = spec
        verdict = await self._limiter.hit(scope, key, limit, window)
        if not verdict.allowed:
            logger.info("Request refused: too many requests ({})", scope)
            raise too_many(verdict, locale)

    async def _breaker(self, locale: Optional[str]) -> None:
        limit = live().api.CODE_MAIL_PER_HOUR
        if limit <= 0:
            return
        verdict = await self._limiter.hit(CODE_ALL_SCOPE, _ALL, limit, HOUR)
        if not verdict.allowed:
            if verdict.count == limit + 1:
                # once per window, the request that trips it
                logger.error(
                    "Sign-in code mail circuit breaker tripped: {} code mails "
                    "requested within the hour (API_CODE_MAIL_PER_HOUR); every "
                    "code request answers 429 until the hour ends. Likely an "
                    "attack: check the access log, and TRUSTED_PROXIES.",
                    limit,
                )
            raise too_many(verdict, locale)

    async def code_mail(
        self,
        client: Optional[str],
        address: str,
        locale: Optional[str] = None,
    ) -> None:
        """Count one request for a sign-in code mail to ``address`` (raises 429
        when a limit is used up). Call it before anything is looked up about
        the address."""
        key = client_key(client)
        # the cheapest refusal first; a request refused by one limit does not
        # use up the budgets after it
        if key != _UNKNOWN:
            await self._hit(CODE_PER_CLIENT, key, locale)
        await self._hit(CODE_PER_ADDRESS, address_limit_key(address), locale)
        await self._breaker(locale)

    async def submit(
        self, client: Optional[str], workspace_id: str, form_id: str
    ) -> None:
        """Count one response submit to a form (raises 429 when the client has
        used up its budget on it). Nothing is counted for an unknown client."""
        key = client_key(client)
        if key == _UNKNOWN:
            return
        await self._hit(SUBMIT_PER_CLIENT_FORM, f"{key}\n{workspace_id}:{form_id}")
