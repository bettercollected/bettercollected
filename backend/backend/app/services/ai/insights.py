"""Response summaries & insights (plan §2, phase P3) — strictly opt-in.

Principle #2 of the AI-native plan: the AI never touches respondent data by
default. Generation happens only on an explicit creator action (the POST),
the result is cached so viewing it later reads the cache, not the data, and
the projection is minimising by construction:

- respondent identity (email, data-owner identifier, hidden fields) is NEVER
  projected into the prompt;
- email / phone answer values are redacted before the model sees them —
  the summary reasons about their presence, not their content;
- the prompt forbids reproducing identifying details from free text.
"""

import datetime as dt
import json
import re
from http import HTTPStatus
from typing import Any, Callable, Dict, List, Optional

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
from backend.app.services.ai.prompt_builder import extract_json_object
from backend.app.services.workspace_user_service import WorkspaceUserService

MAX_RESPONSES = 200
MAX_PROJECTION_CHARS = 60_000
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
) -> tuple:
    """Anonymised plain-text projection of responses, within the char budget.

    Returns (projection_text, included_count).
    """
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
        workspace_user_service: WorkspaceUserService,
        provider_resolver: Callable,
        form_repo: FormRepository,
        workspace_form_repo: WorkspaceFormRepository,
        form_response_repo: FormResponseRepository,
        insight_repo: FormAIInsightRepository,
    ):
        self._workspace_user_service = workspace_user_service
        self._provider_resolver = provider_resolver
        self._form_repo = form_repo
        self._workspace_form_repo = workspace_form_repo
        self._form_response_repo = form_response_repo
        self._insight_repo = insight_repo

    async def _authorize(
        self, workspace_id: PydanticObjectId, form_id: str, user: User
    ) -> FormDocument:
        await self._workspace_user_service.check_user_has_access_in_workspace(
            workspace_id=workspace_id, user=user
        )
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
        return form_document

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
        form_document = await self._authorize(workspace_id, form_id, user)

        total = await self._form_response_repo.count_responses_for_form_ids([form_id])
        if total == 0:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                content="This form has no responses to summarize yet.",
            )
        responses = await self._form_response_repo.list_recent_by_form_id(
            form_id, MAX_RESPONSES
        )
        form = StandardForm(**form_document.model_dump())
        projection, included = project_responses(workspace_id, form, responses)
        if not included:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                content="No readable answers found in this form's responses.",
            )

        provider = self._provider_resolver(request.provider)
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
            **payload, response_count=included, total_responses=total, generated_at=now
        )
