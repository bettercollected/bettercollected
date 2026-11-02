"""The default words of an email action that replaced the built-in "send me a
copy" action: the subject it had and the answers of the response, in English
and in Dutch (formal "u"), plus a link to the responses.

Plain text with the placeholders every template may use (``{{form_title}}``,
``{{answers}}``); nothing here is computed from an answer. The link is a
literal address built from the web app's address, the workspace name and the
form id (``builtin_actions.links.responses_link``), so it is written once, when
the action is made, and is not a placeholder."""

from __future__ import annotations

from typing import Optional, Tuple

from backend.app.schemas.email_action import EmailTemplate

SUBJECT_EN = "You have got a new response in {{form_title}}"
SUBJECT_NL = "U heeft een nieuwe reactie ontvangen op {{form_title}}"
LINK_LINE_EN = "View all responses: {link}"
LINK_LINE_NL = "Bekijk alle reacties: {link}"


def default_templates(link: Optional[str] = None) -> Tuple[EmailTemplate, EmailTemplate]:
    """``(en, nl)`` default templates: the answers block, then, when a ``link``
    is given, a line with it."""

    def body(line: str) -> str:
        return "{{answers}}" + (f"\n\n{line.format(link=link)}" if link else "")

    return (
        EmailTemplate(subject=SUBJECT_EN, body=body(LINK_LINE_EN)),
        EmailTemplate(subject=SUBJECT_NL, body=body(LINK_LINE_NL)),
    )
