from pydantic import BaseModel, Field


class FormActionsDto(BaseModel):
    name: str
    value: str
    type: str


MAX_SECRET_CHARS = 64 * 1024


class RunSecretDto(BaseModel):
    """A secret the executor hands back in plain for the backend to seal: the
    name of one the form's action already holds, and its new value."""

    name: str = Field(min_length=1, max_length=200)
    value: str = Field(min_length=1, max_length=MAX_SECRET_CHARS)
    type: str = "secrets"
