"""Elastic APM without what a request's URL (and, strictly, its headers, body,
a stack frame's variables or a database error's parameters) may carry, for
every service that traces.

The APM agent records each request's full URL, its headers and cookies, the
body when ``CAPTURE_BODY`` asks for it, the URL of every outgoing HTTP call
(span ``context.http.url``), the local variables of stack frames (errors by
default; spans and transactions too with ``COLLECT_LOCAL_VARIABLES``) and an
exception's message, which for a database error lists the statement's
parameters. A processor built by :func:`make_processor` cleans every
transaction, span and error event before it is sent:

* always: no query string or fragment in the request URL, an event's name, a
  referer header, a span's ``context.http.url`` or a URL in its
  ``context.destination``; and whatever ``redact`` replaces in them (the
  backend's receipt numbers);
* ``strict``: also no request headers, cookies, body or environment, no local
  variables in any stack frame (errors and spans), and no ``[parameters: ...]``
  in an exception or log message. For a service whose requests carry secrets
  in those places (auth: the internal key header, the sign-in code).

:func:`private_client_class` builds the APM client class that always loads the
processor, so the agent's ``ELASTIC_APM_*`` settings (``PROCESSORS``,
``CAPTURE_BODY``, ``CAPTURE_HEADERS``, ``SANITIZE_FIELD_NAMES``,
``COLLECT_LOCAL_VARIABLES``) can't switch it off; with ``strict`` it also
keeps ``COLLECT_LOCAL_VARIABLES`` at ``off``. A processor that fails drops the
event (the agent's own rule).

``common`` does not depend on elastic-apm; only :func:`private_client_class`
imports it, from the service that has it installed.
"""

import re
from typing import Any, Callable, Dict, Optional
from urllib.parse import urlsplit, urlunsplit

# the agent's event types (elasticapm.conf.constants ERROR, SPAN, TRANSACTION)
EVENT_TYPES = frozenset({"transaction", "span", "error"})
# keys under context.request.url that hold (part of) the query string
_QUERY_KEYS = ("search", "query", "query_string", "raw", "hash")
_REFERER_HEADERS = ("referer", "referrer")
# what strict mode drops from context.request
_REQUEST_DETAILS = ("headers", "cookies", "body", "env")
# SQLAlchemy's error text: "...[SQL: ...]\n[parameters: (...)]\n(Background on ..."
_SQL_PARAMETERS = re.compile(
    r"\[parameters: .*?(?=\n\(Background on this error|\Z)", re.DOTALL
)
_PARAMETERS_REDACTED = "[parameters: redacted]"


def _same(text: str) -> str:
    return text


def without_query(url: str, redact: Callable[[str], str] = _same) -> str:
    """``url`` without query string and fragment, then ``redact`` applied."""
    parts = urlsplit(url)
    return redact(urlunsplit((parts.scheme, parts.netloc, parts.path, "", "")))


def _text_without_query(text: str, redact: Callable[[str], str]) -> str:
    """A URL (or a path) without query string and fragment."""
    if "://" in text:
        return without_query(text, redact)
    return redact(text.split("?", 1)[0].split("#", 1)[0])


def without_parameters(text: str) -> str:
    """``text`` with a database error's ``[parameters: ...]`` replaced."""
    return _SQL_PARAMETERS.sub(_PARAMETERS_REDACTED, text)


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
        event["name"] = _text_without_query(event["name"], redact)
    if strict:
        for key in ("exception", "log", "stacktrace"):
            _drop_frame_variables(event.get(key))
        _redact_messages(event)
    context = event.get("context") or {}
    _redact_span_context(context, redact)
    request = context.get("request")
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


def _redact_span_context(context: Dict[str, Any], redact) -> None:
    """A span's outgoing URL (``http.url``) and any URL in ``destination``."""
    http = context.get("http")
    if isinstance(http, dict) and isinstance(http.get("url"), str):
        http["url"] = _text_without_query(http["url"], redact)
    destination = context.get("destination")
    if isinstance(destination, dict):
        for holder in (destination, destination.get("service")):
            if not isinstance(holder, dict):
                continue
            for key, value in holder.items():
                if isinstance(value, str) and ("?" in value or "#" in value):
                    holder[key] = _text_without_query(value, redact)


def _redact_messages(event: Dict[str, Any]) -> None:
    """No database parameters in an exception's (or its causes') or a log's
    message, nor in the culprit."""
    exception = event.get("exception")
    pending = [exception] if isinstance(exception, dict) else []
    while pending:
        current = pending.pop()
        if isinstance(current.get("message"), str):
            current["message"] = without_parameters(current["message"])
        pending.extend(c for c in current.get("cause") or [] if isinstance(c, dict))
    log = event.get("log")
    if isinstance(log, dict):
        for key in ("message", "param_message"):
            if isinstance(log.get(key), str):
                log[key] = without_parameters(log[key])
    if isinstance(event.get("culprit"), str):
        event["culprit"] = without_parameters(event["culprit"])


def make_processor(
    redact: Callable[[str], str] = _same, *, strict: bool = False
) -> Callable[[Any, Dict[str, Any]], Dict[str, Any]]:
    """An APM processor (``(client, event) -> event``) for transactions,
    spans and errors, running :func:`redact_event`."""

    def redact_apm_event(client: Any, event: Dict[str, Any]) -> Dict[str, Any]:
        return redact_event(event, redact, strict)

    redact_apm_event.event_types = set(EVENT_TYPES)  # what elasticapm's for_events sets
    return redact_apm_event


def private_client_class(
    processor: Callable[[Any, Dict[str, Any]], Dict[str, Any]],
    ignore_url: Optional[Callable[[str], bool]] = None,
    *,
    strict: bool = False,
) -> type:
    """An ``elasticapm.Client`` subclass that always runs ``processor`` last
    and never traces a URL ``ignore_url`` matches, whatever its settings.
    ``strict``: local variables are never collected either (the processor
    drops them too, should a setting bring them back)."""
    from elasticapm import Client

    class PrivateAPMClient(Client):
        """The APM client with common.utils.apm_privacy built in."""

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            if strict:  # set outright: the environment outranks a config dict
                self.config.collect_local_variables = "off"

        def load_processors(self):
            return [*super().load_processors(), processor]

        def should_ignore_url(self, url):
            if ignore_url is not None and ignore_url(str(url)):
                return True
            return super().should_ignore_url(url)

    return PrivateAPMClient
