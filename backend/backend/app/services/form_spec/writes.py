"""Create, replace and edit forms from form spec documents (the public API).

Every write goes through the product's own paths: a created form through
``WorkspaceFormService.create_form``, a replaced one through
``WorkspaceFormService.update_form`` (the builder's save, written
conditionally), operations through ``persist_ops_to_form`` (the ops engine
MCP and the builder chat use). Nothing here bypasses their checks.

Versions: a form's ETag is its draft's ``updated_at`` (milliseconds) and a
hash of its spec document, so it changes with every save and with every
change of the trust settings, which live on the workspace association.

Replacing: the document replaces the form's content (title, welcome page,
pages, endings, theme, hidden fields, section titles). In ``trust`` and
``logo`` a key left out keeps its stored value ("" clears a text; the logo
image itself is only set by uploading it), as everywhere else.
"""

import datetime as dt
import hashlib
import json
from http import HTTPStatus
from typing import Any, Dict, List, Optional, Tuple

from common.ids import RecordId
from common.form_spec import FormSpec, spec_to_form, spec_trust_settings
from common.form_spec.adapters import SpecConversionError
from common.models.standard_form import (
    LayoutType,
    StandardForm,
    StandardFormSettings,
    ThankYouPageField,
    WelcomePageField,
)
from common.models.user import User
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool

from backend.app.exceptions import HTTPException
from backend.app.services.ai.chat import _persist_settings_ops, persist_ops_to_form
from backend.app.services.ai.ops import (
    FormSettingsPatch,
    OpResult,
    UpdateFormSettingsOp,
    applied,
    apply_settings_ops,
    parse_ops,
    too_many_ops,
)
from backend.app.services.form_concurrency import FORM_CHANGED_CODE
from backend.app.services.form_spec.checks import check_spec_document
from backend.app.services.form_spec.diff import spec_diff
from backend.app.services.form_spec.service import (
    FormSpecService,
    ops_errors,
)
from backend.app.services.workspace_form_service import keep_section_titles

PRECONDITION_FAILED_CODE = "precondition_failed"
PRECONDITION_REQUIRED_CODE = "precondition_required"
INVALID_SPEC_CODE = "invalid_spec"
OPS_FAILED_CODE = "ops_failed"

_EPOCH = dt.datetime(1970, 1, 1, tzinfo=dt.timezone.utc)
# the trust keys the association holds besides the policy link and retention,
# written through the settings op semantics (apply_settings_ops)
_PATCH_KEYS = (
    "purpose",
    "retention_text",
    "require_verified_identity",
    "allow_editing_response",
    "show_submission_number",
)


def _ms(value: Optional[dt.datetime]) -> int:
    if value is None:
        return 0
    if value.tzinfo is None:
        value = value.replace(tzinfo=dt.timezone.utc)
    delta = value - _EPOCH
    return delta.days * 86_400_000 + delta.seconds * 1000 + delta.microseconds // 1000


def form_etag(updated_at: Optional[dt.datetime], document: Dict[str, Any]) -> str:
    canonical = json.dumps(document, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode()).hexdigest()[:16]
    return f'"{_ms(updated_at):x}-{digest}"'


def parse_if_match(value: Optional[str]) -> Optional[List[str]]:
    """The entity tags of an If-Match header (weak ones compared as
    strong), ``["*"]`` for any; None without the header."""
    if value is None or not value.strip():
        return None
    tags = []
    for part in value.split(","):
        part = part.strip()
        if part.startswith("W/"):
            part = part[2:]
        if part:
            tags.append(part)
    return tags or None


def precondition_failed() -> HTTPException:
    return HTTPException(
        status_code=HTTPStatus.PRECONDITION_FAILED,
        content={
            "code": PRECONDITION_FAILED_CODE,
            "message": "The form changed since the version your If-Match names. "
            "Fetch it again and reapply your change.",
        },
    )


def precondition_required() -> HTTPException:
    return HTTPException(
        status_code=HTTPStatus.PRECONDITION_REQUIRED,
        content={
            "code": PRECONDITION_REQUIRED_CODE,
            "message": "Send If-Match with the form's ETag (from GET) to "
            "replace it.",
        },
    )


def _invalid_spec(errors: List[Dict[str, str]]) -> HTTPException:
    return HTTPException(
        status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        content={
            "code": INVALID_SPEC_CODE,
            "message": "The document is not a valid form spec.",
            "errors": errors,
        },
    )


async def _checked_spec(raw: Any) -> FormSpec:
    """The spec of a document that passes every check, else 422 with all
    its errors. CPU-bound on a large document: off the event loop."""
    result = await run_in_threadpool(check_spec_document, raw)
    if not result["valid"]:
        raise _invalid_spec(result["errors"])
    return FormSpec.model_validate(raw)


def with_builder_defaults(form: StandardForm) -> StandardForm:
    """A welcome page and an ending when the form brings none, like the
    builder's new form (the respondent's post-submit screen needs one)."""
    if form.welcome_page is None:
        form.welcome_page = WelcomePageField(
            title="", layout=LayoutType.SINGLE_COLUMN_NO_BACKGROUND
        )
    if not form.thankyou_page:
        form.thankyou_page = [
            ThankYouPageField(layout=LayoutType.SINGLE_COLUMN_NO_BACKGROUND)
        ]
    return form


def _trust_patch(spec: FormSpec) -> Optional[UpdateFormSettingsOp]:
    trust = spec_trust_settings(spec)
    values = {k: trust[k] for k in _PATCH_KEYS if k in trust}
    if not values:
        return None
    return UpdateFormSettingsOp(patch=FormSettingsPatch(**values))


async def _write_trust(
    workspace_id: RecordId, form_id: str, spec: FormSpec
) -> None:
    """The document's trust settings, on this workspace's association only."""
    op = _trust_patch(spec)
    if op is not None:
        result = OpResult(index=0, op=op.op, ok=True, message="")
        await _persist_settings_ops(
            form_id, [op], [result], workspace_id=workspace_id
        )


def _replacement(existing: StandardForm, settings: Any, spec: FormSpec) -> StandardForm:
    """The form a replace stores (before the save's own settling)."""
    try:
        form = spec_to_form(spec)
    except SpecConversionError as error:
        raise _invalid_spec(error.errors)
    form.form_id = existing.form_id
    for page in form.fields or []:
        # left out: cleared (a save keeps a title it is not sent)
        if page.properties is not None and page.properties.section_title is None:
            page.properties.section_title = ""
    if form.hidden_fields is None:
        form.hidden_fields = []
    for name in ("logo_position", "logo_alt", "use_workspace_logo"):
        if getattr(form, name, None) is None:
            setattr(form, name, getattr(existing, name, None))
    form.logo = existing.logo
    # The form's own settings stay; the policy link and retention come from
    # the document, or else from the association (where they are kept).
    own = (
        existing.settings.model_copy(deep=True)
        if existing.settings
        else StandardFormSettings()
    )
    trust = spec_trust_settings(spec)
    for key in (
        "privacy_policy_url",
        "response_expiration_type",
        "response_expiration",
    ):
        stored = getattr(settings, key, None) if settings is not None else None
        setattr(own, key, trust.get(key, stored))
    # The language: left out, the form keeps its own; null clears it.
    if "language" in spec.model_fields_set:
        own.language = spec.language
    form.settings = own
    return form


def _settings_preview(settings: Any, spec: FormSpec) -> Any:
    if settings is None:
        return None
    preview = settings.model_copy(deep=True)
    trust = spec_trust_settings(spec)
    for key in ("response_expiration_type", "response_expiration"):
        if key in trust:
            setattr(preview, key, trust[key])
    if "privacy_policy_url" in trust:
        preview.privacy_policy_url = (trust["privacy_policy_url"] or "").strip() or None
    op = _trust_patch(spec)
    if op is not None:
        apply_settings_ops(
            preview, [op], [OpResult(index=0, op=op.op, ok=True, message="")]
        )
    return preview


class FormSpecWriter:
    def __init__(
        self,
        form_spec_service: FormSpecService,
        workspace_form_service,
        workspace_form_repo,
        form_repo,
    ):
        self._spec = form_spec_service
        self._workspace_forms = workspace_form_service
        self._workspace_form_repo = workspace_form_repo
        self._form_repo = form_repo

    async def _load(self, workspace_id: RecordId, form_id: str):
        """(stored draft, StandardForm, association settings), 404 otherwise."""
        form, settings = await self._spec.load(workspace_id, form_id)
        document = await self._form_repo.get_form_document_by_id(str(form_id))
        if document is None:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND, content="Form not found"
            )
        return document, form, settings

    async def read(
        self, workspace_id: RecordId, form_id: str
    ) -> Tuple[Dict[str, Any], str]:
        """(spec document, ETag)."""
        document, form, settings = await self._load(workspace_id, form_id)
        spec = self._spec.spec_of(form, settings)
        return spec, form_etag(document.updated_at, spec)

    @staticmethod
    def _check_if_match(tags: Optional[List[str]], current: str) -> None:
        if tags is not None and "*" not in tags and current not in tags:
            raise precondition_failed()

    async def create(
        self, workspace_id: RecordId, raw: Any, user: User
    ) -> Tuple[str, Dict[str, Any], str]:
        """Create a draft from a whole document: (form id, spec, ETag).
        All or nothing: the document is checked in full before anything is
        stored."""
        spec = await _checked_spec(raw)
        try:
            form = spec_to_form(spec)
        except SpecConversionError as error:
            raise _invalid_spec(error.errors)
        # the logo is set by uploading it, never from a URL in a document
        form.logo = None
        with_builder_defaults(form)
        created = await self._workspace_forms.create_form(
            workspace_id=workspace_id, form=form, user=user
        )
        await _write_trust(workspace_id, created.form_id, spec)
        document, etag = await self.read(workspace_id, created.form_id)
        return created.form_id, document, etag

    async def replace(
        self,
        workspace_id: RecordId,
        form_id: str,
        raw: Any,
        if_match: Optional[List[str]],
        user: User,
    ) -> Tuple[Dict[str, Any], str]:
        """Replace a form from a whole document, only while it is still the
        version ``if_match`` names: 428 without it, 412 when stale (also
        when another save lands between the check and the write)."""
        if if_match is None:
            raise precondition_required()
        document, existing, settings = await self._load(workspace_id, form_id)
        current = form_etag(document.updated_at, self._spec.spec_of(existing, settings))
        self._check_if_match(if_match, current)
        spec = await _checked_spec(raw)
        form = _replacement(existing, settings, spec)
        try:
            await self._workspace_forms.update_form(
                workspace_id=workspace_id,
                form_id=RecordId(form_id),
                form=form,
                user=user,
                expected_updated_at=document.updated_at or _EPOCH,
            )
        except HTTPException as error:
            if _is_form_changed(error):
                raise precondition_failed() from error
            raise
        await _write_trust(workspace_id, form_id, spec)
        return await self.read(workspace_id, form_id)

    async def publish(
        self, workspace_id: RecordId, form_id: str, user: User
    ) -> Dict[str, Any]:
        """Publish through the product's publish (its checks included):
        ``{formId, published, slug}``."""
        await self._load(workspace_id, form_id)  # 404 for another workspace's
        await self._workspace_forms.publish_form(
            workspace_id=workspace_id, form_id=RecordId(form_id), user=user
        )
        association = await self._workspace_form_repo.find_workspace_form(
            workspace_id, form_id
        )
        slug = (
            association.settings.custom_url
            if association and association.settings
            else None
        )
        return {"formId": form_id, "published": True, "slug": slug}

    async def preview_replace(
        self, workspace_id: RecordId, form_id: str, raw: Any
    ) -> Dict[str, Any]:
        """What a replace with ``raw`` would store, and the diff from now:
        ``{valid, errors, warnings, form, diff}``. Stores nothing."""
        _, existing, settings = await self._load(workspace_id, form_id)
        before = self._spec.spec_of(existing, settings)
        result = await run_in_threadpool(check_spec_document, raw)
        out = {
            "valid": result["valid"],
            "errors": result["errors"],
            "warnings": result["warnings"],
            "form": None,
            "diff": None,
        }
        if not result["valid"]:
            return out

        def compute() -> None:
            spec = FormSpec.model_validate(raw)
            form = _replacement(existing, settings, spec)
            keep_section_titles(form, None)  # "" -> cleared, as the save does
            after = self._spec.spec_of(form, _settings_preview(settings, spec))
            out["form"] = after
            out["diff"] = spec_diff(before, after)

        # CPU-bound on a large form (the diff above all): off the event loop
        await run_in_threadpool(compute)
        return out

    async def apply_ops(
        self,
        workspace_id: RecordId,
        form_id: str,
        raw_ops: List[Any],
        atomic: bool,
        if_match: Optional[List[str]],
    ) -> Tuple[Dict[str, Any], str]:
        """Apply an op batch (the ops engine MCP uses). With ``if_match``
        the form is written only while it is still that version (412).
        Atomic and any op failed: 422 ``ops_failed``, nothing stored."""
        refusal = too_many_ops(len(raw_ops))
        if refusal:
            raise HTTPException(
                status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
                content={
                    "code": "too_many_ops",
                    "message": refusal,
                    "errors": [{"path": "/ops", "message": refusal}],
                },
            )
        try:
            ops = parse_ops(raw_ops)
        except ValidationError as error:
            errors = ops_errors(error)
            raise HTTPException(
                status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
                content={
                    "code": "invalid_ops",
                    "message": "The operations are not valid.",
                    "errors": errors,
                },
            ) from error
        document, form, settings = await self._load(workspace_id, form_id)
        expected = None
        if if_match is not None:
            current = form_etag(document.updated_at, self._spec.spec_of(form, settings))
            self._check_if_match(if_match, current)
            expected = document.updated_at or _EPOCH
        try:
            _, results, _ = await persist_ops_to_form(
                document,
                form,
                ops,
                workspace_id=workspace_id,
                atomic=atomic,
                expected_updated_at=expected,
            )
        except HTTPException as error:
            if _is_form_changed(error):
                raise precondition_failed() from error
            raise
        if atomic and not all(r.ok for r in results):
            raise HTTPException(
                status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
                content={
                    "code": OPS_FAILED_CODE,
                    "message": "An operation failed, so none was applied.",
                    "errors": [
                        {"path": f"/ops/{r.index}", "message": r.message}
                        for r in results
                        if not r.ok
                    ],
                },
            )
        spec, etag = await self.read(workspace_id, form_id)
        return (
            {
                "applied": applied(results, atomic),
                "atomic": atomic,
                "results": [r.model_dump(mode="json", by_alias=True) for r in results],
                "form": spec,
            },
            etag,
        )


def _is_form_changed(error: HTTPException) -> bool:
    content = error.content
    return (
        error.status_code == HTTPStatus.CONFLICT
        and isinstance(content, dict)
        and content.get("code") == FORM_CHANGED_CODE
    )
