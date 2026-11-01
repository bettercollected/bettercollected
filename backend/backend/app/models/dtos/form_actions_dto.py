from typing import Literal

from pydantic import BaseModel, Field


class FormActionsDto(BaseModel):
    name: str
    value: str
    type: str


MAX_SECRET_CHARS = 64 * 1024


# the only secret an executor refreshes: the Google credential
CREDENTIAL_SECRET = "Credentials"


class RunSecretDto(BaseModel):
    """The refreshed credential the executor hands back in plain for the backend
    to seal: its name is always ``Credentials`` (any other name is refused), and
    its new value. It only replaces a ``Credentials`` secret the form's action
    already holds."""

    name: Literal["Credentials"]
    value: str = Field(min_length=1, max_length=MAX_SECRET_CHARS)
    type: str = "secrets"
