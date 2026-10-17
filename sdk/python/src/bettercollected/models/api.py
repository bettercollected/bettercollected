# Generated from docs/api/public-v1.openapi.json by scripts/generate.py. Do not edit.

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class CreatedForm(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
    )
    form_id: str = Field(..., alias="formId", title="Formid")
    form: dict[str, Any] = Field(
        ...,
        description="A form spec v1 document (bettercollected.models.spec.FormSpec).",
    )


class DeletionRequestInfo(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
    )
    status: str = Field(..., description="pending or success.", title="Status")


class ErrorItem(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
    )
    path: str = Field(
        ...,
        description='A JSON pointer into the request body ("" for the body as a whole).',
        title="Path",
    )
    message: str = Field(..., title="Message")


class FormSummary(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
    )
    form_id: str = Field(..., alias="formId", title="Formid")
    title: str | None = Field(None, title="Title")
    slug: str | None = Field(
        None, description="The share slug of the form.", title="Slug"
    )
    published: bool = Field(..., title="Published")
    updated_at: str | None = Field(
        None, alias="updatedAt", description="ISO 8601.", title="Updatedat"
    )


class OpResult(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
    )
    index: int = Field(..., title="Index")
    op: str = Field(..., title="Op")
    ok: bool = Field(..., title="Ok")
    message: str = Field(..., title="Message")
    created_id: str | None = Field(None, alias="createdId", title="Createdid")


class OpsResult(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
    )
    applied: bool = Field(
        ..., description="Whether the batch changed the form.", title="Applied"
    )
    atomic: bool = Field(..., title="Atomic")
    results: list[OpResult] = Field(..., title="Results")
    form: dict[str, Any] = Field(
        ...,
        description="A form spec v1 document (bettercollected.models.spec.FormSpec).",
    )


class PublishResult(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
    )
    form_id: str = Field(..., alias="formId", title="Formid")
    published: Literal[True] = Field(..., title="Published")
    slug: str | None = Field(None, title="Slug")


class ReplacePreview(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
    )
    valid: bool = Field(..., title="Valid")
    errors: list[ErrorItem] = Field(..., title="Errors")
    warnings: list[ErrorItem] = Field(..., title="Warnings")
    form: dict[str, Any] | None = Field(
        None, description="What PUT would store (when valid)."
    )
    diff: dict[str, Any] | None = Field(
        None, description="From the stored form to that one (when valid).", title="Diff"
    )


class ResponseDetail(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
    )
    response_id: str = Field(..., alias="responseId", title="Responseid")
    form_id: str = Field(..., alias="formId", title="Formid")
    submitted_at: str | None = Field(None, alias="submittedAt", title="Submittedat")
    answers: dict[str, Any] = Field(..., description="By field id.", title="Answers")
    internal_answers: dict[str, Any] = Field(
        ...,
        alias="internalAnswers",
        description="Values staff entered in the form's internal fields, by field id.",
        title="Internalanswers",
    )
    deletion_request: DeletionRequestInfo | None = Field(None, alias="deletionRequest")


class ResponseSummary(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
    )
    response_id: str = Field(..., alias="responseId", title="Responseid")
    form_id: str = Field(..., alias="formId", title="Formid")
    submitted_at: str | None = Field(None, alias="submittedAt", title="Submittedat")
    answer_count: int | None = Field(None, alias="answerCount", title="Answercount")
    deletion_request: DeletionRequestInfo | None = Field(
        None,
        alias="deletionRequest",
        description="Set when the respondent asked for this response to be deleted: honour it in every copy you keep.",
    )


class ValidationResult(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
    )
    valid: bool = Field(..., title="Valid")
    errors: list[ErrorItem] = Field(..., title="Errors")
    warnings: list[ErrorItem] = Field(
        ...,
        description="Not blocking: checks a publish applies, read-only values.",
        title="Warnings",
    )
    compliance: dict[str, Any] = Field(
        ...,
        description="The organisation's compliance rules are only checked by the AI review, never here.",
        title="Compliance",
    )


class OpsRequest(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
    )
    ops: list[dict[str, Any]] = Field(
        ...,
        description="Edit operations, applied in order (docs/api/README.md, 'Operations'). At most 200.",
        title="Ops",
    )
    atomic: bool | None = Field(
        True,
        description="All or nothing (the default here): when any operation fails, nothing is stored and every error is returned.",
        title="Atomic",
    )


class DryRunResult(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
    )
    ok: bool = Field(..., description="Whether every operation applied.", title="Ok")
    applied: bool = Field(
        ..., description="Whether the batch would change the form.", title="Applied"
    )
    atomic: bool = Field(..., title="Atomic")
    form: dict[str, Any] = Field(
        ...,
        description="A form spec v1 document (bettercollected.models.spec.FormSpec).",
    )
    diff: dict[str, Any] = Field(
        ...,
        description="Pages and fields added, removed, moved and changed, with JSON pointer paths, and the form-level changes.",
        title="Diff",
    )
    results: list[OpResult] = Field(..., title="Results")


class Error(BaseModel):
    """
    Every error the API answers.
    """

    model_config = ConfigDict(
        populate_by_name=True,
    )
    code: str = Field(
        ...,
        description="Stable, for programs: e.g. unauthorized, missing_scope, not_found, invalid_spec, precondition_failed, rate_limited.",
        title="Code",
    )
    message: str = Field(..., description="For people.", title="Message")
    errors: list[ErrorItem] | None = Field(None, title="Errors")


class FormList(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
    )
    items: list[FormSummary] = Field(..., title="Items")
    page: int = Field(..., title="Page")
    size: int = Field(..., title="Size")
    total: int = Field(..., title="Total")


class ResponseList(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
    )
    items: list[ResponseSummary] = Field(..., title="Items")
    page: int = Field(..., title="Page")
    size: int = Field(..., title="Size")
    total: int = Field(..., title="Total")
