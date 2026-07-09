"""Compliance copilot (plan §2 'compliance copilot', phase P2) — one-click
review of a form against the workspace's compliance profile plus baseline
privacy checks. The trust design language, automated.

Stateless: a review reads the draft and proposes findings; nothing changes
until the creator applies a fix, and fixes go through the same typed-ops
pipeline as chat editing (``persist_ops_to_form`` — one write path, never
two). Every finding is visible and individually applied; no bulk silent
rewrite.
"""

from http import HTTPStatus
from typing import Any, Callable, Dict, List, Literal, Optional

from beanie import PydanticObjectId
from common.models.standard_form import StandardForm
from common.models.user import User
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from backend.app.exceptions import HTTPException
from backend.app.models.dtos.response_dtos import StandardFormCamelModel
from backend.app.schemas.standard_form import FormDocument
from backend.app.schemas.workspace_form import WorkspaceFormDocument
from backend.app.services.ai.chat import persist_ops_to_form
from backend.app.services.ai.ops import OpResult, parse_ops
from backend.app.services.ai.profile import AIProfileService, render_prompt_block
from backend.app.services.ai.prompt_builder import (
    OPS_GUIDE,
    extract_json_object,
    project_form,
)
from backend.app.services.workspace_user_service import WorkspaceUserService

# Baseline checks that apply to every form, before any org-specific rules.
# Kept in the prompt (not code) deliberately: the checks reason about intent
# ("does this free-text invite PII?"), which is the model's job — the schema
# and ops validation stay code's job.
BASELINE_CHECKS = """\
Baseline privacy checks (apply to EVERY form, in addition to the organization's rules):
1. Purpose: does the form tell respondents why this data is collected? A missing or vague purpose is a finding (severity: medium).
2. Data minimisation: flag fields that collect personal data the form's purpose doesn't obviously need (severity: high for sensitive data, else medium).
3. Free-text PII: flag long/short text questions whose phrasing invites personal data that a structured, less identifying field could collect (severity: medium).
4. Consent: consent must be an explicit opt-in question, never implied, never pre-ticked, and never bundled with unrelated agreements (severity: high).
5. Sensitive data: health, exact age or birthdate, government identifiers, financial details, biometrics — flag unless the purpose clearly requires them, and prefer coarser alternatives (age ranges, yes/no eligibility) (severity: high).
6. Required-field pressure: flag questions marked required that the purpose doesn't justify requiring (severity: info).
Do NOT invent problems: if the form is clean, return an empty findings list and say so in the summary."""

REVIEW_OUTPUT_CONTRACT = """\
Respond with a single JSON object and nothing else:
{"summary": "<2-3 sentences, plain language, addressed to the form's creator>",
 "findings": [{"severity": "high"|"medium"|"info",
               "message": "<what is wrong and why it matters, one or two sentences>",
               "fieldId": "<id of the affected field, or null if it concerns the whole form>",
               "fix": {"description": "<what the fix does, one sentence>", "ops": [<operations>]} or null}]}
Order findings most severe first. Include a fix ONLY when typed operations can actually correct the finding; advice-only findings get "fix": null."""


class _CamelModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)


class FormAIReviewRequest(_CamelModel):
    provider: Optional[str] = None


class ReviewFix(_CamelModel):
    description: str
    ops: List[Dict[str, Any]]


class ReviewFinding(_CamelModel):
    severity: Literal["high", "medium", "info"]
    message: str
    field_id: Optional[str] = None
    fix: Optional[ReviewFix] = None


class FormAIReviewResponse(_CamelModel):
    summary: str
    findings: List[ReviewFinding] = []


class ApplyReviewFixRequest(_CamelModel):
    ops: List[Dict[str, Any]] = Field(..., min_length=1)


class ApplyReviewFixResponse(_CamelModel):
    results: List[OpResult] = []
    form: dict
    # Present when a fix changed form settings (purpose/retention/…).
    settings: Optional[dict] = None


def build_review_system_prompt(form_snapshot: str, profile) -> str:
    """System prompt for a compliance review.

    The org's compliance section is the primary rulebook (rendered with its
    usual elevated wording); baseline checks cover forms in workspaces that
    haven't written one yet.
    """
    parts = [
        "You are the compliance reviewer inside BetterCollected, a privacy-first form builder. "
        "Review the form below and report problems a privacy-conscious organization would want fixed before publishing.",
        BASELINE_CHECKS,
        "## Current form snapshot\n<form_snapshot>\n" + form_snapshot + "\n</form_snapshot>",
    ]
    block = render_prompt_block(profile)
    if block:
        parts.append(block)
    parts.append(
        "When you propose a fix, use the typed operations described next.\n\n" + OPS_GUIDE
    )
    parts.append(REVIEW_OUTPUT_CONTRACT)
    return "\n\n".join(parts)


def _coerce_finding(raw: Dict[str, Any]) -> Optional[ReviewFinding]:
    """One malformed finding must not sink the review — validate each
    independently, and drop a fix whose ops don't parse (the finding's
    message still has value; a broken fix does not)."""
    if not isinstance(raw, dict) or not str(raw.get("message") or "").strip():
        return None
    severity = raw.get("severity")
    if severity not in ("high", "medium", "info"):
        severity = "info"
    fix = None
    raw_fix = raw.get("fix")
    if isinstance(raw_fix, dict) and raw_fix.get("ops"):
        try:
            parse_ops(raw_fix["ops"])
            fix = ReviewFix(
                description=str(raw_fix.get("description") or "Apply the suggested change"),
                ops=raw_fix["ops"],
            )
        except Exception:
            fix = None
    field_id = raw.get("fieldId") or raw.get("field_id")
    return ReviewFinding(
        severity=severity,
        message=str(raw["message"]).strip(),
        field_id=str(field_id) if field_id else None,
        fix=fix,
    )


class FormAIReviewService:
    def __init__(
        self,
        workspace_user_service: WorkspaceUserService,
        provider_resolver: Callable,
    ):
        self._workspace_user_service = workspace_user_service
        self._provider_resolver = provider_resolver

    async def _load_form(
        self, workspace_id: PydanticObjectId, form_id: str, user: User
    ) -> FormDocument:
        await self._workspace_user_service.check_user_has_access_in_workspace(
            workspace_id=workspace_id, user=user
        )
        # The form must belong to THIS workspace (same rule as chat and MCP).
        association = await WorkspaceFormDocument.find_one(
            WorkspaceFormDocument.workspace_id == workspace_id,
            WorkspaceFormDocument.form_id == form_id,
        )
        form_document = (
            await FormDocument.find_one({"form_id": form_id}) if association else None
        )
        if not form_document:
            raise HTTPException(status_code=HTTPStatus.NOT_FOUND, content="Form not found")
        return form_document, association

    async def review(
        self,
        workspace_id: PydanticObjectId,
        form_id: str,
        request: FormAIReviewRequest,
        user: User,
    ) -> FormAIReviewResponse:
        form_document, association = await self._load_form(workspace_id, form_id, user)
        form = StandardForm(**form_document.model_dump())
        profile = await AIProfileService.get_profile_for_prompt(workspace_id)
        # The snapshot includes trust settings — a review that can't see the
        # stated purpose/retention would flag them as missing forever.
        system = build_review_system_prompt(
            project_form(form, settings=association.settings), profile
        )

        provider = self._provider_resolver(request.provider)
        raw_reply = await provider.chat(
            system, [{"role": "user", "content": "Review this form now."}]
        )

        try:
            parsed = extract_json_object(raw_reply)
            summary = str(parsed.get("summary") or "").strip()
            raw_findings = parsed.get("findings")
            if not summary or not isinstance(raw_findings, list):
                raise ValueError("missing summary/findings")
        except Exception:
            raise HTTPException(
                status_code=HTTPStatus.BAD_GATEWAY,
                content="The AI returned an unusable review — please try again.",
            )

        findings = [f for f in (_coerce_finding(r) for r in raw_findings) if f]
        severity_rank = {"high": 0, "medium": 1, "info": 2}
        findings.sort(key=lambda f: severity_rank[f.severity])
        return FormAIReviewResponse(summary=summary, findings=findings)

    async def apply_fix(
        self,
        workspace_id: PydanticObjectId,
        form_id: str,
        request: ApplyReviewFixRequest,
        user: User,
    ) -> ApplyReviewFixResponse:
        form_document, _ = await self._load_form(workspace_id, form_id, user)
        try:
            ops = parse_ops(request.ops)
        except Exception:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST, content="Invalid fix operations"
            )
        form = StandardForm(**form_document.model_dump())
        new_form, results, updated_settings = await persist_ops_to_form(form_document, form, ops)
        return ApplyReviewFixResponse(
            results=results,
            form=StandardFormCamelModel(**new_form.model_dump()).model_dump(
                mode="json", by_alias=True
            ),
            settings=updated_settings,
        )
