"""Elastic APM and the privacy of a request's URL.

The APM agent records each request's full URL (and the transaction name of a
route it cannot match is the raw path), which would bring back what the
request log leaves out: the typed search in the query string and the receipt
number in a by-uuid path. Two guards, both independent of the agent's
configuration (an ``ELASTIC_APM_*`` variable cannot switch them off):

* receipt routes (``/by-uuid/``) are not traced at all;
* every transaction and error event is cleaned by :func:`redact_apm_event`
  before it is sent: no query string anywhere, receipt numbers redacted.
"""

from typing import Any, Dict
from urllib.parse import urlsplit, urlunsplit

from elasticapm import Client
from elasticapm.conf.constants import ERROR, TRANSACTION
from elasticapm.processors import for_events

from backend.app.middlewares.request_privacy import redact_receipts

# keys under context.request.url that hold (part of) the query string
_QUERY_KEYS = ("search", "query", "query_string", "raw", "hash")
_REFERER_HEADERS = ("referer", "referrer")


def _without_query(url: str) -> str:
    """``url`` without query string and fragment (and receipts redacted)."""
    parts = urlsplit(url)
    return redact_receipts(urlunsplit((parts.scheme, parts.netloc, parts.path, "", "")))


@for_events(ERROR, TRANSACTION)
def redact_apm_event(client: Any, event: Dict[str, Any]) -> Dict[str, Any]:
    """An APM processor: strips the query string and receipt numbers from the
    request URL, the transaction name and a referer header of the event."""
    if isinstance(event.get("name"), str):  # the raw path when no route matched
        event["name"] = redact_receipts(event["name"].split("?", 1)[0])
    request = (event.get("context") or {}).get("request")
    if not isinstance(request, dict):
        return event
    url = request.get("url")
    if isinstance(url, dict):
        for key in _QUERY_KEYS:
            url.pop(key, None)
        for key in ("full", "pathname"):
            if isinstance(url.get(key), str):
                url[key] = _without_query(url[key])
    elif isinstance(url, str):
        request["url"] = _without_query(url)
    headers = request.get("headers")
    if isinstance(headers, dict):
        for name in list(headers):
            if name.lower() in _REFERER_HEADERS and isinstance(headers[name], str):
                headers[name] = _without_query(headers[name])
    return event


class PrivateAPMClient(Client):
    """The APM client with the guards above built in."""

    def load_processors(self):
        return [*super().load_processors(), redact_apm_event]

    def should_ignore_url(self, url):
        return "/by-uuid/" in str(url) or super().should_ignore_url(url)
