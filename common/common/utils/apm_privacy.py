"""Elastic APM without what a request's URL (and, strictly, its headers, body or
a stack frame's variables) may carry, for every service that traces.

The APM agent records each request's full URL, its headers and cookies, the
body when ``CAPTURE_BODY`` asks for it, and the local variables of the frames
of an error. A processor built by :func:`make_processor` cleans every
transaction and error event before it is sent:

* always: no query string or fragment in the URL, the transaction name or a
  referer header, and whatever ``redact`` replaces in them (the backend's
  receipt numbers);
* ``strict``: also no request headers, cookies, body or environment, and no
  local variables in any stack frame. For a service whose requests carry
  secrets in those places (auth: the internal key header, the sign-in code).

:func:`private_client_class` builds the APM client class that always loads the
processor: the agent's ``ELASTIC_APM_*`` settings (``PROCESSORS``,
``CAPTURE_BODY``, ``CAPTURE_HEADERS``, ``SANITIZE_FIELD_NAMES``) can't switch it
off. A processor that fails drops the event (the agent's own rule).

``common`` does not depend on elastic-apm; only :func:`private_client_class`
imports it, from the service that has it installed.
"""

from typing import Any, Callable, Dict, Optional
from urllib.parse import urlsplit, urlunsplit

# the agent's event types (elasticapm.conf.constants ERROR, TRANSACTION)
EVENT_TYPES = frozenset({"transaction", "error"})
# keys under context.request.url that hold (part of) the query string
_QUERY_KEYS = ("search", "query", "query_string", "raw", "hash")
_REFERER_HEADERS = ("referer", "referrer")
# what strict mode drops from context.request
_REQUEST_DETAILS = ("headers", "cookies", "body", "env")


def _same(text: str) -> str:
    return text


def without_query(url: str, redact: Callable[[str], str] = _same) -> str:
    """``url`` without query string and fragment, then ``redact`` applied."""
    parts = urlsplit(url)
    return redact(urlunsplit((parts.scheme, parts.netloc, parts.path, "", "")))


def _drop_frame_variables(node: Any) -> None:
    if isinstance(node, dict):
        node.pop("vars", None)
        for value in node.values():
            _drop_frame_variables(value)
    elif isinstance(node, list):
        for value in node:
            _drop_frame_variables(value)


def redact_event(
    event: Dict[str, Any],
    redact: Callable[[str], str] = _same,
    strict: bool = False,
) -> Dict[str, Any]:
    """``event`` cleaned in place (see the module docstring); returned."""
    if isinstance(event.get("name"), str):  # the raw path when no route matched
        event["name"] = redact(event["name"].split("?", 1)[0].split("#", 1)[0])
    if strict:
        for key in ("exception", "log"):
            _drop_frame_variables(event.get(key))
    request = (event.get("context") or {}).get("request")
    if not isinstance(request, dict):
        return event
    url = request.get("url")
    if isinstance(url, dict):
        for key in _QUERY_KEYS:
            url.pop(key, None)
        for key in ("full", "pathname"):
            if isinstance(url.get(key), str):
                url[key] = without_query(url[key], redact)
    elif isinstance(url, str):
        request["url"] = without_query(url, redact)
    if strict:
        for key in _REQUEST_DETAILS:
            request.pop(key, None)
        return event
    headers = request.get("headers")
    if isinstance(headers, dict):
        for name in list(headers):
            if name.lower() in _REFERER_HEADERS and isinstance(headers[name], str):
                headers[name] = without_query(headers[name], redact)
    return event


def make_processor(
    redact: Callable[[str], str] = _same, *, strict: bool = False
) -> Callable[[Any, Dict[str, Any]], Dict[str, Any]]:
    """An APM processor (``(client, event) -> event``) for transactions and
    errors, running :func:`redact_event`."""

    def redact_apm_event(client: Any, event: Dict[str, Any]) -> Dict[str, Any]:
        return redact_event(event, redact, strict)

    redact_apm_event.event_types = set(EVENT_TYPES)  # what elasticapm's for_events sets
    return redact_apm_event


def private_client_class(
    processor: Callable[[Any, Dict[str, Any]], Dict[str, Any]],
    ignore_url: Optional[Callable[[str], bool]] = None,
) -> type:
    """An ``elasticapm.Client`` subclass that always runs ``processor`` last
    and never traces a URL ``ignore_url`` matches, whatever its settings."""
    from elasticapm import Client

    class PrivateAPMClient(Client):
        """The APM client with common.utils.apm_privacy built in."""

        def load_processors(self):
            return [*super().load_processors(), processor]

        def should_ignore_url(self, url):
            if ignore_url is not None and ignore_url(str(url)):
                return True
            return super().should_ignore_url(url)

    return PrivateAPMClient
