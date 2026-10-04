"""Response summaries & insights (plan §2, phase P3) — strictly opt-in.

Principle #2 of the AI-native plan: the AI never touches respondent data by
default. It needs three things (#716): the workspace AI opt-in (#715), the
form's own "Allow AI insights on responses" setting (admins only, recorded
with who and when; while on, respondents see a notice naming the provider),
and an admin clicking generate. Only forms collected by BetterCollected
qualify (an imported form's respondents answered on the provider's page,
which has no notice), and only their own responses submitted after the
setting was turned on, i.e. after the notice was shown, are ever sent. The result is
cached so viewing it later reads the cache, not the data, and the projection
is minimising by construction:

- respondent identity (email, data-owner identifier, hidden fields) is NEVER
  projected into the prompt;
- email / phone answer values are redacted before the model sees them —
  the summary reasons about their presence, not their content;
- internal (staff-only) fields and their answers are left out, also when
  the field was internal only in an older version of the form;
- free-text answers are sent as written (the UI says so), and the prompt
  forbids reproducing identifying details from them.
"""

import datetime as dt
import json
import re
from http import HTTPStatus
from typing import Any, Callable, Dict, Iterable, List, Optional, Set

from beanie import PydanticObjectId
from common.models.standard_form import StandardForm
from common.models.user import User
from common.services.crypto_service import crypto_service
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from backend.app.exceptions import HTTPException
from backend.app.repositories.form_ai_insight_repository import FormAIInsightRepository
from backend.app.repositories.form_repository import FormRepository
from backend.app.repositories.form_response_repository import FormResponseRepository
from backend.app.repositories.workspace_form_repository import WorkspaceFormRepository
from backend.app.schemas.form_ai_insight import FormAIInsightDocument
from backend.app.schemas.standard_form import FormDocument
from backend.app.schemas.standard_form_response import FormResponseDocument
from backend.app.services.ai.consent import (
    AIConsentService,
    provider_name,
)
from backend.app.services.ai.prompt_builder import extract_json_object
from backend.app.services.form_response_service import FormResponseService
from backend.app.services.internal_fields import (
    internal_field_ids,
    strip_internal_fields,
)
from backend.app.services.authorization_service import AuthorizationService
from backend.app.models.enum.permission import Permission

MAX_RESPONSES = 200
MAX_PROJECTION_CHARS = 60_000
# forms built and collected in BetterCollected; anything else was imported
SELF_PROVIDER = "self"
REDACTED_TYPES = {"email": "[email provided]", "phone_number": "[phone provided]"}

INSIGHTS_SYSTEM_PROMPT = """\
You are the response-insights assistant inside BetterCollected, a privacy-first form builder. \
You will receive a form's questions and a batch of anonymised responses. Summarize what the responses say, for the form's creator.

Privacy rules (hard requirements):
- NEVER reproduce names, email addresses, phone numbers, or any other identifying detail from the responses, even partially.
- Reason in aggregate. A short quote (8 words or fewer) is allowed only if it contains nothing identifying.
- If the data is too sparse to support a claim, say so instead of inventing one.

Respond with a single JSON object and nothing else:
{"summary": "<3-5 sentences: what the responses collectively say>",
 "themes": [{"title": "<short theme name>", "description": "<1-2 sentences>", "approxCount": <int or null>}],
 "actionable": ["<concrete follow-up the creator could take>", ...],
 "sentiment": "<one sentence on overall tone, or null if not meaningful>"}
Order themes by how many responses support them. 3-6 themes, 1-4 actionable items."""


class _CamelModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)


class FormAIInsightsRequest(_CamelModel):
    provider: Optional[str] = None


AI_INSIGHTS_NOT_ENABLED = "ai_insights_not_enabled"


class FormAIInsightsSettingsRequest(_CamelModel):
    enabled: bool


class FormAIInsightsSettingsDto(_CamelModel):
    enabled: bool
    provider: Optional[str] = None
    provider_name: Optional[str] = None
    enabled_by: Optional[str] = None
    enabled_at: Optional[dt.datetime] = None


def _insights_not_enabled(message: str) -> HTTPException:
    return HTTPException(
        status_code=HTTPStatus.FORBIDDEN,
        content={"code": AI_INSIGHTS_NOT_ENABLED, "message": message},
    )


def _aware(value: Optional[dt.datetime]) -> Optional[dt.datetime]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=dt.timezone.utc)
    return value


def collected_by_bettercollected(association) -> bool:
    """Whether respondents filled this form in BetterCollected, where the AI
    notice is shown. An imported form's respondents answered on the
    provider's own page (Google Forms, Typeform), which never shows it."""
    settings = getattr(association, "settings", None)
    return getattr(settings, "provider", None) == SELF_PROVIDER


def submitted_here(
    responses: List[FormResponseDocument],
) -> List[FormResponseDocument]:
    """Only responses submitted through BetterCollected; a response imported
    from a provider is never analysed, whatever its timestamp."""
    return [r for r in responses if getattr(r, "provider", None) == SELF_PROVIDER]


def submitted_since(
    responses: List[FormResponseDocument], since: dt.datetime
) -> List[FormResponseDocument]:
    """Responses submitted at or after ``since`` (when respondents started
    seeing the AI notice); one without a timestamp is left out."""
    since = _aware(since)
    return [
        r
        for r in responses
        if _aware(getattr(r, "created_at", None)) is not None
        and _aware(r.created_at) >= since
    ]


class InsightTheme(_CamelModel):
    title: str
    description: str
    approx_count: Optional[int] = None


class FormAIInsightsResponse(_CamelModel):
    summary: str
    themes: List[InsightTheme] = []
    actionable: List[str] = []
    sentiment: Optional[str] = None
    response_count: int
    total_responses: int
    generated_at: dt.datetime
    # only responses submitted from this moment on were analysed
    analysed_since: Optional[dt.datetime] = None


def _question_titles(form: StandardForm) -> Dict[str, str]:
    """fieldId -> plain question title, tolerating v2 pages and v1 flat forms."""
    titles: Dict[str, str] = {}

    def visit(fields):
        for f in fields or []:
            if isinstance(f.title, str) and f.title:
                titles[f.id] = f.title
            if f.properties and f.properties.fields:
                visit(f.properties.fields)

    visit(form.fields)
    return titles


def _choice_labels(form: StandardForm) -> Dict[str, str]:
    """choiceId -> human label. Responses store choice IDs; the model should
    see what the respondent actually picked, not a UUID."""
    labels: Dict[str, str] = {}

    def visit(fields):
        for f in fields or []:
            if f.properties:
                for choice in f.properties.choices or []:
                    if choice.id and choice.value:
                        labels[choice.id] = choice.value
                visit(f.properties.fields)

    visit(form.fields)
    return labels


_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def _resolve_choice(value: str, labels: Dict[str, str]) -> str:
    """Choice ID -> label; an unmapped UUID (older form version) projects as
    a neutral marker instead of leaking meaningless IDs into the prompt."""
    if value in labels:
        return labels[value]
    return "[selected option]" if _UUID_RE.match(value) else value


def _answer_text(raw: Any, choice_labels: Dict[str, str]) -> Optional[str]:
    """One answer -> plain text, with identifying value types redacted and
    choice IDs resolved to their labels."""
    answer = (
        raw
        if isinstance(raw, dict)
        else raw.model_dump() if hasattr(raw, "model_dump") else None
    )
    if not answer:
        return None
    answer_type = str(answer.get("type") or "")
    if answer_type in REDACTED_TYPES:
        return REDACTED_TYPES[answer_type]
    if answer.get("text"):
        return str(answer["text"])
    if answer.get("number") is not None:
        return str(answer["number"])
    if answer.get("boolean") is not None:
        return "yes" if answer["boolean"] else "no"
    if answer.get("date"):
        return str(answer["date"])
    choice = answer.get("choice")
    if isinstance(choice, dict) and choice.get("value"):
        return _resolve_choice(str(choice["value"]), choice_labels)
    choices = answer.get("choices")
    if isinstance(choices, dict) and choices.get("values"):
        return ", ".join(
            _resolve_choice(str(v), choice_labels) for v in choices["values"]
        )
    if answer.get("file_url") or answer.get("file_metadata"):
        return "[file uploaded]"
    if answer.get("url"):
        return str(answer["url"])
    return None


def project_responses(
    workspace_id: PydanticObjectId,
    form: StandardForm,
    responses: List[FormResponseDocument],
    internal_ids: Iterable[str] = (),
) -> tuple:
    """Anonymised plain-text projection of responses, within the char budget.

    ``internal_ids`` adds field ids that are internal in other versions of
    the form than ``form`` (see ``all_internal_field_ids``).

    Returns (projection_text, included_count).
    """
    # internal (staff-only) fields and their answers never reach the model
    internal_ids: Set[str] = internal_field_ids(form) | {str(i) for i in internal_ids}
    form = strip_internal_fields(form.model_copy(deep=True))
    titles = _question_titles(form)
    choice_labels = _choice_labels(form)
    blocks: List[str] = []
    used = 0
    included = 0
    for index, response in enumerate(responses, start=1):
        answers = response.answers
        if isinstance(answers, (bytes, str)):
            answers = json.loads(
                crypto_service.decrypt(
                    workspace_id=workspace_id, form_id=response.form_id, data=answers
                )
            )
        if not isinstance(answers, dict):
            continue
        lines = []
        for field_id, raw in answers.items():
            if str(field_id) in internal_ids:
                continue
            text = _answer_text(raw, choice_labels)
            if not text:
                continue
            question = titles.get(field_id, "Question")
            lines.append(f"  {question}: {text[:500]}")
        if not lines:
            continue
        block = f"Response {index}:\n" + "\n".join(lines)
        if used + len(block) > MAX_PROJECTION_CHARS:
            break
        blocks.append(block)
        used += len(block)
        included += 1
    return "\n\n".join(blocks), included


class FormAIInsightsService:
    def __init__(
        self,
        authorization_service: AuthorizationService,
        provider_resolver: Callable,
        form_repo: FormRepository,
        workspace_form_repo: WorkspaceFormRepository,
        form_response_repo: FormResponseRepository,
        insight_repo: FormAIInsightRepository,
        ai_consent_service: Optional[AIConsentService] = None,
        form_response_service: Optional[FormResponseService] = None,
    ):
        self._authorization = authorization_service
        self._form_response_service = form_response_service
        self._ai_consent = ai_consent_service
        self._provider_resolver = provider_resolver
        self._form_repo = form_repo
        self._workspace_form_repo = workspace_form_repo
        self._form_response_repo = form_response_repo
        self._insight_repo = insight_repo

    async def _authorize(
        self,
        workspace_id: PydanticObjectId,
        form_id: str,
        user: User,
        permission: Permission = Permission.RESPONSE_READ,
    ) -> tuple:
        # Insights summarise respondents' answers: whoever may read them.
        # Allowing them on a form is an AI opt-in (ai.manage).
        await self._authorization.authorize(user, permission, workspace_id)
        association = await self._workspace_form_repo.find_workspace_form(
            workspace_id, form_id
        )
        form_document = (
            await self._form_repo.get_form_document_by_id(form_id)
            if association
            else None
        )
        if not form_document:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND, content="Form not found"
            )
        return form_document, association

    async def update_settings(
        self,
        workspace_id: PydanticObjectId,
        form_id: str,
        request: FormAIInsightsSettingsRequest,
        user: User,
    ) -> FormAIInsightsSettingsDto:
        """Turn "Allow AI insights on responses" on or off (ai.manage).
        Turning it on needs the workspace AI opt-in and records the provider
        the respondent notice names, who, and when."""
        _, association = await self._authorize(
            workspace_id, form_id, user, Permission.AI_MANAGE
        )
        settings = association.settings
        if request.enabled:
            self._require_collected_here(association)
            provider = await self._ai_consent.require_enabled(workspace_id)
            settings.ai_insights_enabled = True
            settings.ai_insights_provider = provider
            settings.ai_insights_provider_name = provider_name(provider)
            settings.ai_insights_enabled_by = str(user.id)
            settings.ai_insights_enabled_at = dt.datetime.now(dt.timezone.utc)
        else:
            settings.ai_insights_enabled = False
            settings.ai_insights_provider = None
            settings.ai_insights_provider_name = None
            settings.ai_insights_enabled_by = None
            settings.ai_insights_enabled_at = None
        await self._workspace_form_repo.save(association)
        return self.settings_dto(settings)

    @staticmethod
    def settings_dto(settings) -> FormAIInsightsSettingsDto:
        enabled = bool(settings and settings.ai_insights_enabled)
        return FormAIInsightsSettingsDto(
            enabled=enabled,
            provider=settings.ai_insights_provider if enabled else None,
            provider_name=settings.ai_insights_provider_name if enabled else None,
            enabled_by=settings.ai_insights_enabled_by if enabled else None,
            enabled_at=settings.ai_insights_enabled_at if enabled else None,
        )

    @staticmethod
    def _require_collected_here(association) -> None:
        if not collected_by_bettercollected(association):
            raise _insights_not_enabled(
                "AI insights are only available for forms collected with "
                "BetterCollected. This form's respondents answered on another "
                "service and never saw the AI notice."
            )

    async def _require_insights_allowed(
        self, workspace_id: PydanticObjectId, association
    ) -> dt.datetime:
        """The moment respondents started seeing the notice, or 403: the form
        must be collected here and allow AI insights, for the provider (and,
        for a compatible endpoint, the host) the notice named."""
        self._require_collected_here(association)
        settings = association.settings
        if not settings or not settings.ai_insights_enabled:
            raise _insights_not_enabled(
                "AI insights are off for this form. A workspace admin can allow "
                "them in the form's settings; only responses submitted after that "
                "are analysed."
            )
        consented = await self._ai_consent.require_enabled(workspace_id)
        # The name is compared too: for the compatible provider it carries the
        # endpoint's host, so a changed COMPAT_BASE_URL needs a fresh notice.
        if (
            settings.ai_insights_provider != consented
            or settings.ai_insights_provider_name != provider_name(consented)
            or not settings.ai_insights_enabled_at
        ):
            raise _insights_not_enabled(
                "Respondents were told a different AI provider. Turn AI insights "
                "off and on again for this form to show them the current one."
            )
        return settings.ai_insights_enabled_at

    async def get_cached(
        self, workspace_id: PydanticObjectId, form_id: str, user: User
    ) -> Optional[FormAIInsightsResponse]:
        await self._authorize(workspace_id, form_id, user)
        document = await self._insight_repo.find(workspace_id, form_id)
        if not document:
            return None
        return FormAIInsightsResponse(
            **document.payload,
            response_count=document.response_count,
            total_responses=document.total_responses,
            generated_at=document.generated_at,
        )

    async def generate(
        self,
        workspace_id: PydanticObjectId,
        form_id: str,
        request: FormAIInsightsRequest,
        user: User,
    ) -> FormAIInsightsResponse:
        """The explicit opt-in action — the only moment the AI reads answers."""
        form_document, association = await self._authorize(workspace_id, form_id, user)
        # The workspace's AI opt-in (#715) and the form's own setting (#716)
        # before any response is read.
        provider = await self._provider_resolver(workspace_id, request.provider)
        since = await self._require_insights_allowed(workspace_id, association)

        total = await self._form_response_repo.count_responses_for_form_ids([form_id])
        if total == 0:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                content="This form has no responses to summarize yet.",
            )
        # Newest first: every response submitted after the notice is newer
        # than any submitted before it, so filtering the latest ones is enough.
        # Defence in depth: never a response imported from a provider.
        responses = submitted_since(
            submitted_here(
                await self._form_response_repo.list_recent_by_form_id(
                    form_id, MAX_RESPONSES
                )
            ),
            since,
        )
        if not responses:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                content=(
                    "No responses were submitted since AI insights were allowed "
                    "for this form. Only those are analysed."
                ),
            )
        form = StandardForm(**form_document.model_dump())
        # internal in the draft, the published or any older version
        internal_ids = await self._form_response_service.all_internal_field_ids(
            form_id, every_version=True
        )
        projection, included = project_responses(
            workspace_id, form, responses, internal_ids
        )
        if not included:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                content="No readable answers found in this form's responses.",
            )

        raw_reply = await provider.chat(
            INSIGHTS_SYSTEM_PROMPT,
            [
                {
                    "role": "user",
                    "content": f"Form title: {form.title}\n\nResponses ({included} of {total} total):\n\n{projection}",
                }
            ],
        )
        try:
            parsed = extract_json_object(raw_reply)
            summary = str(parsed.get("summary") or "").strip()
            if not summary:
                raise ValueError("missing summary")
            themes = [
                InsightTheme(
                    title=str(t.get("title") or "").strip(),
                    description=str(t.get("description") or "").strip(),
                    approx_count=(
                        t.get("approxCount")
                        if isinstance(t.get("approxCount"), int)
                        else None
                    ),
                )
                for t in (parsed.get("themes") or [])
                if isinstance(t, dict) and t.get("title")
            ]
            actionable = [
                str(a) for a in (parsed.get("actionable") or []) if isinstance(a, str)
            ]
            sentiment = str(parsed["sentiment"]) if parsed.get("sentiment") else None
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(
                status_code=HTTPStatus.BAD_GATEWAY,
                content="The AI returned an unusable summary — please try again.",
            )

        payload = {
            "summary": summary,
            "themes": [t.model_dump() for t in themes],
            "actionable": actionable,
            "sentiment": sentiment,
            "analysed_since": _aware(since).isoformat(),
        }
        now = dt.datetime.now(dt.timezone.utc)
        document = await self._insight_repo.find(workspace_id, form_id)
        if document:
            document.payload = payload
            document.response_count = included
            document.total_responses = total
            document.generated_by = user.id
            document.generated_at = now
        else:
            document = FormAIInsightDocument(
                workspace_id=workspace_id,
                form_id=form_id,
                payload=payload,
                response_count=included,
                total_responses=total,
                generated_by=user.id,
                generated_at=now,
            )
        await self._insight_repo.save(document)
        return FormAIInsightsResponse(
            **payload,
            response_count=included,
            total_responses=total,
            generated_at=now,
        )
