"""Stored record of a form's email action (``services/email_actions``): who is
mailed when a response is submitted, and the words of the mail. It holds the
templates the form's admins wrote and the staff addresses they chose (members
of the workspace); no answer. Deliveries are logged in the shared action log
(``schemas/webhook.py`` ``ActionLogDocument``, type ``email``): ids and codes,
never an address."""

from typing import List, Optional

from common.records import Record, RecordId
from pydantic import BaseModel

from backend.app.schemas.webhook import ActionCondition, WebhookField


class EmailTemplate(BaseModel):
    """One language's subject and body (plain text, ``{{placeholders}}``)."""

    subject: str
    body: str


class FormEmailActionDocument(Record):
    workspace_id: RecordId
    form_id: str
    name: str
    enabled: bool = False
    # the form's language picks one (``nl*`` -> nl, anything else -> en)
    en: EmailTemplate
    nl: EmailTemplate
    # the questions the templates may name: ``source`` in the form's variables
    # namespace, ``key`` the placeholder name
    fields: List[WebhookField] = []
    # fixed addresses (normalised) of members of the workspace
    team_recipients: List[str] = []
    # an ``email`` question whose answer receives a copy of its own submission
    respondent_field: Optional[str] = None
    # runs only when it holds on the submitted answers (None: every submission)
    condition: Optional[ActionCondition] = None
    created_by: Optional[str] = None
    updated_by: Optional[str] = None

    class Settings:
        name = "form_email_actions"
