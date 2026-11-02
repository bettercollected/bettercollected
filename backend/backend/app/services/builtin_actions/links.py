"""Links in what the built-in actions send."""

from __future__ import annotations

from urllib.parse import quote


def responses_link(client_url: str, workspace_name: str, form_id: str) -> str:
    """The form's responses page on the web app, as the Slack and Discord
    messages and the mail of the built-in actions linked to it. The workspace
    name and the form id are percent-encoded, so neither can end the path (or
    close the link of a chat message)."""
    return (
        f"{(client_url or '').rstrip('/')}/{quote(str(workspace_name), safe='')}"
        f"/dashboard/forms/{quote(str(form_id), safe='')}/?view=Responses"
    )
