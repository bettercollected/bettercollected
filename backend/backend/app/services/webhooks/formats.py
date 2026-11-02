"""The bodies of the webhook formats the built-in actions used before they moved
into webhooks (``docs/webhooks.md``).

``envelope`` is the signed body of ``payload.py``. The others are the three
bodies the actions executor posted for the built-in "send a webhook", "send to
Slack" and "send to Discord" actions, kept so receivers do not change:

- ``legacy_list``: a JSON list of ``{"field_id", "title", "answer"}`` for every
  question, as ``qa.get_questions_and_answers`` reads it. Also signed (the same
  headers as the envelope; the extra headers break nobody).
- ``slack``: a Slack ``attachments`` message with a link to the responses and a
  field per question.
- ``discord``: a Discord ``embeds`` message, cut to Discord's limits.

Two differences from the executor's chat messages, both for safety: Slack text
values are escaped (``&``, ``<``, ``>``: an answer cannot make a link or a
mention) and a Discord message says it pings nobody (``allowed_mentions``).

The two chat formats carry no signature (the address is the secret). Everything
here is pure: the form and the decrypted answers go in, bytes come out, built at
send time in memory and never stored or queued. The bytes are written the way
the executor wrote them (``json.dumps`` with its defaults) so a receiver that
compares or hashes the body sees no difference.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from backend.app.services.builtin_actions import qa
from backend.app.services.builtin_actions.links import responses_link
from backend.app.services.internal_fields import strip_internal_fields

ENVELOPE = "envelope"
LEGACY_LIST = "legacy_list"
SLACK = "slack"
DISCORD = "discord"
FORMATS = (ENVELOPE, LEGACY_LIST, SLACK, DISCORD)
# the formats whose body carries the signature headers
SIGNED = (ENVELOPE, LEGACY_LIST)
# the formats that send every question and do not use ``fields``
ALL_QUESTION_FORMATS = (LEGACY_LIST, SLACK, DISCORD)
CHAT = (SLACK, DISCORD)

# Discord's limits on an embed's fields
DISCORD_FIELDS_MAX = 25
DISCORD_NAME_MAX = 256
DISCORD_VALUE_MAX = 1024
DASH = "—"


def form_view(form: Any) -> Dict[str, Any]:
    """The published form as the actions executor read it: plain JSON, staff
    information and internal fields removed (``strip_internal_fields``)."""
    copy = form.model_copy(deep=True) if hasattr(form, "model_copy") else form
    stripped = strip_internal_fields(copy)
    if hasattr(stripped, "model_dump"):
        return stripped.model_dump(mode="json")
    return dict(stripped or {})


def response_view(response_id: Optional[str], answers: Dict[str, Any]) -> Dict[str, Any]:
    """What ``qa`` reads of a response: its id and its decrypted answers."""
    return {"response_id": response_id or "", "answers": answers or {}}


def empty_response() -> Dict[str, Any]:
    """The response of a test event: every question, no answer, nothing real."""
    return response_view("", {})


def slack_text(value: Any) -> Any:
    """``value`` as Slack's message formatting wants a text: ``&``, ``<`` and
    ``>`` escaped, so an answer cannot make a link, a mention (``<!channel>``,
    ``<@U123>``) or a broken one. Anything that is not a text is left as it is."""
    if not isinstance(value, str):
        return value
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _dumps(value: Any) -> bytes:
    return json.dumps(value).encode()


def legacy_list_body(form: Dict[str, Any], response: Dict[str, Any]) -> bytes:
    return _dumps(qa.get_questions_and_answers(form, response))


def slack_body(
    form: Dict[str, Any],
    response: Dict[str, Any],
    *,
    workspace_name: str,
    client_url: str,
) -> bytes:
    fields = [
        {
            "title": slack_text(entry["title"]),
            "value": slack_text(entry["answer"]) if entry["answer"] else DASH,
            "short": False,
        }
        for entry in qa.get_questions_and_answers(form, response)
    ]
    link = responses_link(client_url, workspace_name, form.get("form_id"))
    return _dumps(
        {
            "attachments": [
                {
                    "title": f"🎉 **Congratulations!** You received a new response on! `{slack_text(form.get('title'))}`\n\n",
                    "color": "#00FF00",
                    "text": (
                        f"Click <{link}|here> to view the form response.\n\n"
                        "Details:\n"
                    ),
                    "fields": fields,
                    "footer": "Thank you for using Bettercollected",
                }
            ]
        }
    )


def discord_body(
    form: Dict[str, Any],
    response: Dict[str, Any],
    *,
    workspace_name: str,
    client_url: str,
) -> bytes:
    fields: List[Dict[str, Any]] = []
    for entry in qa.get_questions_and_answers(form, response):
        title = str(entry.get("title", "Question")).strip()
        answer = entry.get("answer")
        # Discord refuses an empty value
        value = DASH if answer is None or answer == "" else str(answer).strip()
        title = title[:DISCORD_NAME_MAX] if title else "Untitled"
        value = value[:DISCORD_VALUE_MAX] if value else DASH
        fields.append({"name": title, "value": value, "inline": False})
    fields = fields[:DISCORD_FIELDS_MAX]
    link = responses_link(client_url, workspace_name, form.get("form_id"))
    return _dumps(
        {
            "content": f"🎉 **Congratulations!** You received a new response on **{form.get('title')}**",
            # nothing a respondent or a creator typed pings anyone
            "allowed_mentions": {"parse": []},
            "embeds": [
                {
                    "color": 0x00FF00,
                    "description": (
                        f"[View Form response here]({link})\n"
                        "--------------------------"
                    ),
                    "fields": fields,
                    "footer": {"text": "Thank You for using Bettercollected"},
                }
            ],
        }
    )


def build(
    format_: str,
    form: Dict[str, Any],
    response: Dict[str, Any],
    *,
    workspace_name: str = "",
    client_url: str = "",
) -> bytes:
    """The body of a non-envelope format."""
    if format_ == LEGACY_LIST:
        return legacy_list_body(form, response)
    if format_ == SLACK:
        return slack_body(form, response, workspace_name=workspace_name, client_url=client_url)
    if format_ == DISCORD:
        return discord_body(form, response, workspace_name=workspace_name, client_url=client_url)
    raise ValueError(format_)
