"""Request and response bodies of the public API (camelCase on the wire).

These models describe the API in its OpenAPI document; the endpoints build
their JSON with the services and return it as is."""

from typing import Any, Dict, List, Literal, Optional

from common.form_spec import FormSpec
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from backend.app.services.ai.ops import MAX_OPS_PER_BATCH, OpResult


class _Model(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class ErrorItem(_Model):
    path: str = Field(
        description='A JSON pointer into the request body ("" for '
        "the body as a whole)."
    )
    message: str


class Error(_Model):
    """Every error the API answers."""

    code: str = Field(
        description="Stable, for programs: e.g. unauthorized, "
        "missing_scope, not_found, invalid_spec, precondition_failed, "
        "rate_limited."
    )
    message: str = Field(description="For people.")
    errors: Optional[List[ErrorItem]] = None


class FormSummary(_Model):
    form_id: str
    title: Optional[str] = None
    slug: Optional[str] = Field(None, description="The share slug of the form.")
    published: bool
    updated_at: Optional[str] = Field(None, description="ISO 8601.")


class FormList(_Model):
    items: List[FormSummary]
    page: int
    size: int
    total: int


class CreatedForm(_Model):
    form_id: str
    form: FormSpec


class OpsRequest(_Model):
    ops: List[Dict[str, Any]] = Field(
        ...,
        description="Edit operations, applied in order (docs/api/README.md, "
        f"'Operations'). At most {MAX_OPS_PER_BATCH}.",
    )
    atomic: bool = Field(
        True,
        description="All or nothing (the default here): when any "
        "operation fails, nothing is stored and every error is returned.",
    )


class OpsResult(_Model):
    applied: bool = Field(description="Whether the batch changed the form.")
    atomic: bool
    results: List[OpResult]
    form: FormSpec = Field(description="The form after the batch.")


class DryRunResult(_Model):
    ok: bool = Field(description="Whether every operation applied.")
    applied: bool = Field(description="Whether the batch would change the form.")
    atomic: bool
    form: FormSpec = Field(description="The form the batch would make.")
    diff: Dict[str, Any] = Field(
        description="Pages and fields added, removed, moved and changed, with "
        "JSON pointer paths, and the form-level changes."
    )
    results: List[OpResult]


class ValidationResult(_Model):
    valid: bool
    errors: List[ErrorItem]
    warnings: List[ErrorItem] = Field(
        description="Not blocking: checks a publish applies, read-only values."
    )
    compliance: Dict[str, Any] = Field(
        description="The organisation's compliance rules are only checked by "
        "the AI review, never here."
    )


class ReplacePreview(_Model):
    valid: bool
    errors: List[ErrorItem]
    warnings: List[ErrorItem]
    form: Optional[FormSpec] = Field(
        None, description="What PUT would store (when valid)."
    )
    diff: Optional[Dict[str, Any]] = Field(
        None, description="From the stored form to that one (when valid)."
    )


class PublishResult(_Model):
    form_id: str
    published: Literal[True]
    slug: Optional[str] = None


class DeletionRequestInfo(_Model):
    status: str = Field(description="pending or success.")


class ResponseSummary(_Model):
    response_id: str
    form_id: str
    submitted_at: Optional[str] = None
    answer_count: Optional[int] = None
    deletion_request: Optional[DeletionRequestInfo] = Field(
        None,
        description="Set when the respondent asked for this response to be "
        "deleted: honour it in every copy you keep.",
    )


class ResponseList(_Model):
    items: List[ResponseSummary]
    page: int
    size: int
    total: int


class ResponseDetail(_Model):
    response_id: str
    form_id: str
    submitted_at: Optional[str] = None
    answers: Dict[str, Any] = Field(description="By field id.")
    internal_answers: Dict[str, Any] = Field(
        description="Values staff entered in the form's internal fields, by "
        "field id."
    )
    deletion_request: Optional[DeletionRequestInfo] = None
