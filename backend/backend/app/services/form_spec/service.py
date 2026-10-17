"""Validate a form spec document, read a form as one, and dry-run edit
operations against a form. Nothing here writes."""

from http import HTTPStatus
from typing import Any, Dict, List

from beanie import PydanticObjectId
from common.form_spec import (
    SpecConversionError,
    form_to_spec_dict,
    validation_errors,
)
from common.models.standard_form import StandardForm
from common.models.user import User
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from pydantic.alias_generators import to_camel

from backend.app.exceptions import HTTPException
from backend.app.models.enum.permission import Permission
from backend.app.repositories.form_repository import FormRepository
from backend.app.repositories.workspace_form_repository import (
    WorkspaceFormRepository,
)
from backend.app.services.ai.ops import (
    OP_NAMES,
    OpResult,
    UpdateFormSettingsOp,
    applied,
    apply_form_ops,
    parse_ops,
)
from backend.app.services.authorization_service import AuthorizationService
from backend.app.services.form_spec.checks import check_spec_document
from backend.app.services.form_spec.diff import spec_diff

MAX_DRY_RUN_OPS = 200


class _CamelModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)


class DryRunRequest(_CamelModel):
    ops: List[Dict[str, Any]] = Field(..., max_length=MAX_DRY_RUN_OPS)
    atomic: bool = False


class DryRunResponse(_CamelModel):
    # Whether every op applied, and whether the batch would change the form
    # (atomic: only when every op applied).
    ok: bool
    applied: bool
    atomic: bool
    form: Dict[str, Any]
    diff: Dict[str, Any]
    results: List[OpResult]


def _unprocessable(message: str, errors: List[Dict[str, str]]) -> HTTPException:
    return HTTPException(
        status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        content={"message": message, "errors": errors},
    )


def ops_errors(error: ValidationError) -> List[Dict[str, str]]:
    """Parse errors of an ops payload as ``/ops/<index>/<key>`` (without
    the op name pydantic puts in the location of a tagged union)."""
    errors = []
    for e in validation_errors(error):
        parts = e["path"].split("/")
        # ["", "ops", "<index>", "<op name>", ...]
        if len(parts) > 3 and parts[1] == "ops" and parts[3] in OP_NAMES:
            del parts[3]
        errors.append({"path": "/".join(parts), "message": e["message"]})
    return errors


def settings_after_ops(settings: Any, ops, results: List[OpResult]) -> Any:
    """A copy of the association ``settings`` with the applied
    update_form_settings ops on it, as persist_ops_to_form writes them
    ('' clears a text value)."""
    settings = settings.model_copy(deep=True) if settings is not None else None
    if settings is None:
        return None
    for op, result in zip(ops, results):
        if not result.ok or not isinstance(op, UpdateFormSettingsOp):
            continue
        patch = op.patch
        for key in ("purpose", "retention_text", "privacy_policy_url"):
            value = getattr(patch, key)
            if value is not None:
                setattr(settings, key, value.strip() or None)
        for key in (
            "require_verified_identity",
            "allow_editing_response",
            "show_submission_number",
        ):
            value = getattr(patch, key)
            if value is not None:
                setattr(settings, key, value)
    return settings


class FormSpecService:
    def __init__(
        self,
        authorization_service: AuthorizationService,
        workspace_form_repo: WorkspaceFormRepository,
        form_repo: FormRepository,
    ):
        self._authorization = authorization_service
        self._workspace_form_repo = workspace_form_repo
        self._form_repo = form_repo

    async def validate(
        self, workspace_id: PydanticObjectId, document: Any, user: User
    ) -> Dict[str, Any]:
        await self._authorization.authorize(user, Permission.FORM_EDIT, workspace_id)
        return check_spec_document(document)

    async def load(self, workspace_id: PydanticObjectId, form_id: str):
        """(StandardForm, association settings) of a form of this workspace,
        404 otherwise. Callers authorise first."""
        association = await self._workspace_form_repo.find_workspace_form(
            workspace_id, str(form_id)
        )
        document = (
            await self._form_repo.get_form_document_by_id(str(form_id))
            if association
            else None
        )
        if document is None:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND, content="Form not found"
            )
        return StandardForm(**document.model_dump()), association.settings

    @staticmethod
    def spec_of(form: StandardForm, settings: Any) -> Dict[str, Any]:
        try:
            return form_to_spec_dict(form, settings)
        except SpecConversionError as error:
            raise _unprocessable(str(error), error.errors)

    async def dry_run(
        self,
        workspace_id: PydanticObjectId,
        form_id: str,
        request: DryRunRequest,
        user: User,
    ) -> DryRunResponse:
        await self._authorization.authorize(user, Permission.FORM_EDIT, workspace_id)
        form, settings = await self.load(workspace_id, form_id)
        return self.preview(form, settings, request.ops, request.atomic)

    def preview(
        self,
        form: StandardForm,
        settings: Any,
        raw_ops: List[Dict[str, Any]],
        atomic: bool,
    ) -> DryRunResponse:
        """What ``raw_ops`` would make of ``form``: the resulting spec, the
        diff and per-op results. Stores nothing."""
        before = self.spec_of(form, settings)
        try:
            ops = parse_ops(raw_ops)
        except ValidationError as error:
            raise _unprocessable("The operations are not valid.", ops_errors(error))
        new_form, results = apply_form_ops(form, ops, atomic=atomic)
        did_apply = applied(results, atomic)
        after = (
            self.spec_of(new_form, settings_after_ops(settings, ops, results))
            if did_apply
            else before
        )
        return DryRunResponse(
            ok=all(r.ok for r in results),
            applied=did_apply,
            atomic=atomic,
            form=after,
            diff=spec_diff(before, after),
            results=results,
        )
