"""Stored record of a form's email action (``services/email_actions``): who is
mailed when a response is submitted, and the words of the mail. It holds the
templates the form's admins wrote and the staff addresses they chose (members
of the workspace); no answer. Deliveries are logged in the shared action log
(``schemas/webhook.py`` ``ActionLogDocument``, type ``email``): ids and codes,
never an address."""

from typing import List, Optional

from common.records import Record, RecordId
from pydantic import BaseModel, model_validator

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
    # fixed addresses of members of the workspace (as typed, trimmed)
    team_recipients: List[str] = []
    # a signed-in respondent with a verified account email gets a copy of their
    # own submission, at that account email (never at an address typed in an answer)
    respondent_copy: bool = False
    # runs only when it holds on the submitted answers (None: every submission)
    condition: Optional[ActionCondition] = None
    created_by: Optional[str] = None
    updated_by: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def _earlier_copy_setting(cls, data):
        """A row from before the copy went to the account email held the email
        question it was read from (``respondent_field``): it means "a copy"."""
        if isinstance(data, dict) and "respondent_field" in data:
            data = dict(data)
            if data.pop("respondent_field") and "respondent_copy" not in data:
                data["respondent_copy"] = True
        return data

    class Settings:
        name = "form_email_actions"
