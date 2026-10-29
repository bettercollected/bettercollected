"""BetterCollected's MCP server (plan §2.5) — forms as tools for any LLM.

Transport: stateless streamable-HTTP, mounted at /mcp on the main FastAPI
app. Auth: workspace-scoped API keys as Bearer tokens (see
services/ai/api_keys.py); a pure-ASGI middleware resolves the key into a
contextvar the tools read. Every call lands in the MCP audit log.

Tools deliberately reuse the same services/pipelines as the product —
``update_form`` goes through the exact ops engine the builder chat uses.
"""

import functools
import json
import logging
import unicodedata
from contextvars import ContextVar
from importlib.metadata import version as package_version
from typing import Any, Callable, Dict, List, Optional

from common.ids import RecordId
from common.models.standard_form import StandardForm
from common.models.user import User
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.transport_security import TransportSecuritySettings
from starlette.concurrency import run_in_threadpool

from backend.app.exceptions import HTTPException
from backend.app.models.dtos.request_dtos import AI_PROMPT_MAX_LENGTH, CreateFormWithAI
from backend.app.models.dtos.response_dtos import StandardFormCamelModel
from backend.app.repositories.response_scope import response_scope
from backend.app.schemas.workspace_api_key import WorkspaceAPIKeyDocument
from backend.app.schemas.workspace_form import WorkspaceFormDocument
from backend.app.services.ai.api_keys import APIKeyService
from backend.app.services.api_responses import (
    list_response_summaries,
    response_detail,
)
from backend.app.services.api_access import (
    acting_user,
    audit_key_call,
    require_key_scope,
)
from backend.app.services.ai.chat import persist_ops_to_form
from backend.app.services.ai.ops import applied, parse_ops, too_many_ops
from backend.app.services.ai.profile import AIProfileService
from backend.app.services.form_spec.checks import check_spec_document
from backend.app.services.form_spec.service import (
    DOCUMENT_TOO_LARGE,
    MAX_DOCUMENT_BYTES,
)
from backend.app.services.publish_checks import FORM_NOT_PUBLISHABLE


def _c():
    # Resolved at call time: the container imports services this module depends on.
    from backend.app.container import container

    return container


current_api_key: ContextVar[Optional[WorkspaceAPIKeyDocument]] = ContextVar(
    "current_api_key", default=None
)


class _BetterCollectedMCP(MCPServer):
    """MCPServer whose tools report a refusal in words, as they always have.

    mcp 2.x passes only ``ToolError`` text to the client and turns any other
    exception into a bare "Error executing tool <name>". The tools here refuse
    with ``ValueError`` (pydantic's ValidationError included) or the product's
    ``HTTPException``; both still reach the client with their message, exactly
    as under mcp 1.x. Anything else is a crash, whose text stays on the server.
    """

    def add_tool(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        @functools.wraps(fn)
        async def run(*call_args: Any, **call_kwargs: Any) -> Any:
            try:
                return await fn(*call_args, **call_kwargs)
            except (ValueError, HTTPException) as e:
                raise ToolError(str(e)) from e

        super().add_tool(run, *args, **kwargs)


mcp = _BetterCollectedMCP(
    "bettercollected",
    instructions=(
        "BetterCollected is a privacy-first form builder. Tools operate on the "
        "workspace your API key belongs to. Respect the workspace's AI profile "
        "(get_ai_profile) when creating or editing forms."
    ),
    # serverInfo.version: the SDK's version, as mcp 1.x reported by default.
    version=package_version("mcp"),
)

# mcp 2.x logs every refused call's message at INFO. A refusal can quote the
# caller's input (form text from an op), and 1.x never logged it; crashes
# are still logged, at ERROR.
logging.getLogger("mcp.server.mcpserver.server").setLevel(logging.WARNING)


async def _key(scope: str) -> WorkspaceAPIKeyDocument:
    key = current_api_key.get()
    if key is None:
        raise ValueError("Not authenticated")
    try:
        await require_key_scope(key, scope)
    except HTTPException as e:
        # Our HTTPException carries the message in `content`, which str() drops
        # — re-raise as ValueError so the MCP client sees why it was denied.
        raise ValueError(_error_text(e)) from e
    return key


def _acting_user(key: WorkspaceAPIKeyDocument) -> User:
    return acting_user(key)


# The longest detail an audit entry keeps (an error list can be long).
AUDIT_DETAIL_MAX = 500


async def _audit(tool: str, ok: bool, detail: str = "") -> None:
    key = current_api_key.get()
    if key is not None:
        detail = str(detail or "")
        if len(detail) > AUDIT_DETAIL_MAX:
            detail = detail[: AUDIT_DETAIL_MAX - 1] + "…"
        await audit_key_call(key, tool, ok, detail)


async def _workspace_form_ids(
    workspace_id: RecordId,
) -> Dict[str, WorkspaceFormDocument]:
    docs = await _c().workspace_form_repo().list_in_workspace(workspace_id)
    return {d.form_id: d for d in docs}


def _require_form_in_workspace(form_id: str, workspace_forms: Dict[str, Any]) -> None:
    if form_id not in workspace_forms:
        raise ValueError(f"Form '{form_id}' does not exist in this workspace.")


@mcp.tool()
async def list_forms() -> str:
    """List the workspace's forms: id, title, share slug and publish state."""
    key = await _key("forms:read")
    workspace_forms = await _workspace_form_ids(key.workspace_id)
    forms = await _c().form_repo().get_forms_by_form_ids(list(workspace_forms))
    items = [
        {
            "formId": f.form_id,
            "title": f.title,
            "slug": (
                workspace_forms[f.form_id].settings.custom_url
                if workspace_forms[f.form_id].settings
                else None
            ),
            "published": f.published_at is not None,
        }
        for f in forms
    ]
    await _audit("list_forms", True, f"{len(items)} forms")
    return json.dumps(items)


@mcp.tool()
async def get_form(form_id: str) -> str:
    """Get a form's full structure (pages, fields, settings) as JSON."""
    key = await _key("forms:read")
    workspace_forms = await _workspace_form_ids(key.workspace_id)
    _require_form_in_workspace(form_id, workspace_forms)
    form = await _c().form_repo().get_form_document_by_id(form_id)
    await _audit("get_form", True, form_id)
    return json.dumps(
        StandardFormCamelModel(
            **StandardForm(**form.model_dump()).model_dump()
        ).model_dump(mode="json", by_alias=True, exclude_none=True, exclude={"secrets"})
    )


@mcp.tool()
async def create_form(title: str, description: str = "") -> str:
    """Create a blank draft form (one empty page) — for building precisely
    with update_form ops. Use create_form_with_ai when you want the platform
    to design the form from a prompt instead."""
    key = await _key("forms:write")
    import uuid as _uuid

    from common.models.standard_form import (
        LayoutType,
        StandardFieldProperty,
        StandardFormField,
        StandardFormFieldType,
        ThankYouPageField,
        WelcomePageField,
    )

    from backend.app.container import container

    # Mirror the builder's defaultForm (webapp constants/form.ts): forms need a
    # welcome + thank-you page — the responder's post-submit screen renders
    # thankyouPage, and API-born forms must behave like builder-born ones.
    blank = StandardForm(
        title=title,
        description=description or None,
        builder_version="v2",
        welcome_page=WelcomePageField(
            title="", layout=LayoutType.SINGLE_COLUMN_NO_BACKGROUND
        ),
        thankyou_page=[
            ThankYouPageField(layout=LayoutType.SINGLE_COLUMN_NO_BACKGROUND)
        ],
        fields=[
            StandardFormField(
                id=str(_uuid.uuid4()),
                index=0,
                type=StandardFormFieldType.SLIDE,
                properties=StandardFieldProperty(
                    fields=[], layout=LayoutType.SINGLE_COLUMN_NO_BACKGROUND
                ),
            )
        ],
    )
    form = await container.workspace_form_service().create_form(
        workspace_id=key.workspace_id, form=blank, user=_acting_user(key)
    )
    await _audit("create_form", True, form.form_id)
    return json.dumps({"formId": form.form_id, "title": form.title, "published": False})


@mcp.tool()
async def create_form_with_ai(prompt: str) -> str:
    """Create a new draft form from a natural-language prompt. Generation is
    grounded in the workspace's AI profile (guidelines + compliance)."""
    key = await _key("forms:write")
    from backend.app.container import container

    if not (prompt or "").strip() or len(prompt) > AI_PROMPT_MAX_LENGTH:
        await _audit("create_form_with_ai", False, "prompt length")
        raise ValueError(
            f"The prompt must be between 1 and {AI_PROMPT_MAX_LENGTH} characters."
        )
    try:
        # the same AI limits as the builder (429 ai_rate_limited /
        # ai_daily_limit), counted for the key's creator and workspace
        form = await container.openai_service().create_form_with_ai(
            workspace_id=key.workspace_id,
            create_form_ai=CreateFormWithAI(prompt=prompt),
            user=_acting_user(key),
        )
    except HTTPException as e:
        # e.g. 403 ai_not_enabled or 429: tell the client why, in words
        content = e.content
        message = content.get("message") if isinstance(content, dict) else content
        await _audit("create_form_with_ai", False, str(message or ""))
        raise ValueError(str(message or "Could not create the form")) from e
    await _audit("create_form_with_ai", True, form.form_id)
    return json.dumps({"formId": form.form_id, "title": form.title, "published": False})


def _http_message(error: HTTPException, fallback: str) -> str:
    content = error.content
    if isinstance(content, dict):
        message = content.get("message") or fallback
        errors = content.get("errors")
        if errors:
            message += " " + json.dumps(errors)
        return message
    return str(content or fallback)


@mcp.tool()
async def create_form_outline(prompt: str, document_text: str = "") -> str:
    """Step 1 of two-step AI form creation: the platform's outline of a form
    for a prompt (and optionally the text of a document to base it on):
    title, language, pages with section titles, the questions of each page
    (key, label, type, required, whyWeAsk, choices, validation), show/hide
    rules ("logic") and page jumps ("jumps", "to": a page key or "end").
    Nothing is created. Review or edit the outline, then pass it to
    build_form_from_outline. Same AI opt-in and limits as create_form_with_ai."""
    from backend.app.services.ai.outline_service import (
        DOCUMENT_TEXT_MAX_LENGTH,
        FormOutlineRequest,
    )

    key = await _key("forms:write")
    if not (prompt or "").strip() or len(prompt) > AI_PROMPT_MAX_LENGTH:
        await _audit("create_form_outline", False, "prompt length")
        raise ValueError(
            f"The prompt must be between 1 and {AI_PROMPT_MAX_LENGTH} characters."
        )
    if len(document_text or "") > DOCUMENT_TEXT_MAX_LENGTH:
        await _audit("create_form_outline", False, "document length")
        raise ValueError(
            f"The document text can be at most {DOCUMENT_TEXT_MAX_LENGTH} characters."
        )
    try:
        outline = await _c().form_outline_service().outline(
            workspace_id=key.workspace_id,
            request=FormOutlineRequest(
                prompt=prompt, document_text=document_text or None
            ),
            user=_acting_user(key),
        )
    except HTTPException as e:
        message = _http_message(e, "Could not outline the form")
        await _audit("create_form_outline", False, message)
        raise ValueError(message) from e
    await _audit("create_form_outline", True, f"{len(outline.pages)} pages")
    return json.dumps({"outline": outline.dump()})


@mcp.tool()
async def build_form_from_outline(
    outline: Dict[str, Any], fill_gaps: bool = True
) -> str:
    """Step 2: build an outline (from create_form_outline, edited or not)
    into a new draft form, through the same ops engine as update_form, all
    or nothing. With fill_gaps the platform's AI suggests what the outline
    leaves out (choices of a choice question, the "why we ask" reason of an
    identity question); nothing you wrote is changed. Returns the formId,
    quality findings (codes and ids) and notes on what was adjusted."""
    from backend.app.services.ai.outline_service import (
        BuildFromOutlineRequest,
        outline_validation_problems,
    )

    key = await _key("forms:write")
    parsed, problems = outline_validation_problems(outline)
    if parsed is None:
        await _audit("build_form_from_outline", False, "invalid outline")
        raise ValueError("The outline is not valid: " + "; ".join(problems))
    try:
        result = await _c().form_outline_service().build_response(
            workspace_id=key.workspace_id,
            request=BuildFromOutlineRequest(outline=parsed, fill_gaps=fill_gaps),
            user=_acting_user(key),
        )
    except HTTPException as e:
        message = _http_message(e, "Could not build the form")
        await _audit("build_form_from_outline", False, message)
        raise ValueError(message) from e
    await _audit("build_form_from_outline", True, result.form_id)
    return json.dumps(
        {**result.model_dump(by_alias=True, mode="json"), "published": False}
    )


@mcp.tool()
async def update_form(
    form_id: str, ops: List[Dict[str, Any]], atomic: bool = False
) -> str:
    """Edit a form with typed operations — the same pipeline the builder's AI
    chat uses. Reference page/field ids from get_form. Op shapes (camelCase):
    {"op":"add_field","pageId":str,"field":{"title":str,"type":str,"required"?:bool,
    "placeholder"?:str,"choices"?:[str],"steps"?:int,"internal"?:bool},"afterFieldId"?:str,"index"?:int} ·
    ("internal": a staff-only "for office use" field, never shown to respondents;
    logic cannot depend on it; not allowed inside a repeating group)
    (or "groupId" instead of "pageId": add into a repeating group) ·
    {"op":"add_group","pageId":str,"title":str,"itemLabel":str,"minItems":int,"maxItems":int,
    "itemTitle"?:str,"exportLayout"?:"columns"|"rows","fields":[field]} (repeating group:
    questions filled once per item, e.g. per applicant; no nesting, no file_upload inside) ·
    {"op":"update_field","fieldId":str,"patch":{...same keys as field}} (a date question's
    patch may also set "label":str and "dateRules":[{"comparison":"before"|"after"|"on_or_before"|
    "on_or_after","target":"date"|"today"|"field","date"?:"YYYY-MM-DD","fieldId"?:str}], max 5,
    [] clears; "fieldId" is another date question of the same level or the same group) ·
    {"op":"remove_field","fieldId":str} ·
    {"op":"move_field","fieldId":str,"toPageId"?:str,"toGroupId"?:str,"index":int} ·
    {"op":"add_page","index"?:int,"fields"?:[field]} · {"op":"remove_page","pageId":str} ·
    {"op":"update_form_info","title"?:str,"description"?:str} ·
    {"op":"update_form_settings","patch":{"purpose"?:str,"retentionText"?:str,
    "privacyPolicyUrl"?:str,"requireVerifiedIdentity"?:bool,"allowEditingResponse"?:bool,
    "showSubmissionNumber"?:bool}} (trust metadata; "" clears a text value;
    "retentionText" is an internal note respondents never see, it does not set the
    retention period they are told) ·
    {"op":"set_field_logic","fieldId":str,"logic":{"action":"SHOW"|"HIDE","operator":"AND"|"OR",
    "conditions":[{"fieldId":str,"comparison":"IS_EQUAL"|"IS_NOT_EQUAL"|"CONTAINS"|"IS_EMPTY"|...,
    "value"?:any}]}|null} (conditional visibility; choice values use the LABEL, yes/no uses "Yes"/"No";
    a repeating group is referenced as a whole: "groupMode":"COUNT"|"ANY"|"ALL", with
    "childFieldId" for ANY/ALL; siblings inside a group refer to the same item) ·
    {"op":"set_page_jumps","pageId":str,"jumps":[{"operator":"AND"|"OR","conditions":[...],
    "target":"<page id or __SUBMIT__>","endingId"?:str}]|null} (branching; "__SUBMIT__"
    submits and shows the default ending, or the ending "endingId" names) ·
    {"op":"add_ending","name"?:str,"title"?:str,"message"?:str,"buttonText"?:str,
    "buttonLink"?:str,"isDefault"?:bool,"index"?:int} (a page shown after submitting; "name"
    is internal, at most 60 characters) ·
    {"op":"update_ending","endingId":str,"patch":{...same keys}} ("" clears a text;
    "isDefault":true makes it the ending a plain submit shows) ·
    {"op":"remove_ending","endingId":str} (never the last one; its jumps then show the
    default ending) ·
    {"op":"duplicate_page","pageId":str,"index"?:int} (clone a page, fresh ids) ·
    {"op":"set_section_title","pageId"?:str,"pageIndex"?:int,"title":str|null} (a question
    page's section title, shown by the Leaflet style in the section bar and the welcome
    page's contents list; give pageId or pageIndex (0-based among the question pages); a few
    plain words, at most 120 characters; null or "" clears; not for the welcome page or ending) ·
    {"op":"move_page","pageId":str,"index":int} (0-based among the question pages) ·
    {"op":"set_field_validation","fieldId":str,"validation":{"required"?:bool,"minLength"?:int,
    "maxLength"?:int,"minValue"?:num,"maxValue"?:num,"minChoices"?:int,"maxChoices"?:int,
    "pattern"?:str,"preset"?:"digits"|"letters"|"alphanumeric"}} (absent = unchanged, null clears;
    lengths/pattern: text questions, values: number, choices: multiple choice with several answers) ·
    {"op":"set_question_numbering","pageId"?:str,"show":bool} (no pageId: every page) ·
    {"op":"set_form_language","language":str|null} (the language the form's own text is
    written in, so respondent pages mark it for screen readers: nl, en, de, fr, es, it, pt,
    pl, da, sv, nb or fi; null clears) ·
    {"op":"set_theme_preset","name":str,"style"?:"classic"|"sheet"|"studio"|"leaflet"} (the
    look: a theme preset by name, any case: Leaflet (the default for new forms), Default, Paper,
    Ocean, Forest, Cherry, Mono, Sunset, Lavender, Slate, Blossom, Twilight, Honey, Mint, Sky,
    Rose (Blue, Green, Red, Black, Orange, Purple mean the nearest of these), and the complete
    looks Kantlijn and Raster (faces, corners, buttons, background and the welcome layout too);
    no style = the preset's own (Leaflet, Kantlijn, Raster) or the current one) ·
    {"op":"update_theme","theme":{"title":str,"primary":str,"secondary":str,"tertiary":str,
    "accent":str,"style"?:str,"background"?:{...}}} (exact colours of your own).
    References: add_page, add_field, add_group, duplicate_page and add_ending (and the fields inside
    add_page/add_group) take "ref":"<name>"; later ops in the same call may use "$ref:<name>"
    wherever a page or field id is expected (pageId, fieldId, groupId, afterFieldId, toPageId,
    toGroupId, childFieldId, a jump's target, endingId), conditions and jumps included. Each result
    reports the "createdId". atomic=true applies all ops or none (any error: nothing is stored,
    every error is returned); the default applies what it can. Preview with dry_run_ops.
    At most 200 ops per call.
    Field types: short_text, long_text, email, number, url, phone_number, date,
    yes_no, multiple_choice, dropdown, rating, linear_rating, file_upload, text."""
    key = await _key("forms:write")
    workspace_forms = await _workspace_form_ids(key.workspace_id)
    _require_form_in_workspace(form_id, workspace_forms)
    form_document = await _c().form_repo().get_form_document_by_id(form_id)
    refusal = too_many_ops(len(ops))
    if refusal:
        await _audit("update_form", False, f"{form_id}: {len(ops)} ops refused")
        raise ValueError(refusal)
    parsed = parse_ops(ops)
    form = StandardForm(**form_document.model_dump())
    _, results, updated_settings = await persist_ops_to_form(
        form_document, form, parsed, workspace_id=key.workspace_id, atomic=atomic
    )
    payload = [r.model_dump(by_alias=True) for r in results]
    await _audit(
        "update_form",
        all(r.ok for r in results),
        f"{form_id}: {len(results)} ops" + (" (atomic)" if atomic else ""),
    )
    return json.dumps(
        {
            "applied": applied(results, atomic),
            "results": payload,
            "settings": updated_settings,
        }
    )


@mcp.tool()
async def get_form_spec(form_id: str) -> str:
    """Get a form as a form spec v1 document (docs/spec/README.md): what
    its creator controls, without server-owned data. Page-based forms
    only."""
    key = await _key("forms:read")
    workspace_forms = await _workspace_form_ids(key.workspace_id)
    _require_form_in_workspace(form_id, workspace_forms)
    service = _c().form_spec_service()
    form, settings = await service.load(key.workspace_id, form_id)
    try:
        document = service.spec_of(form, settings)
    except HTTPException as e:
        await _audit("get_form_spec", False, form_id)
        raise ValueError(_error_text(e)) from e
    await _audit("get_form_spec", True, form_id)
    return json.dumps(document)


@mcp.tool()
async def validate_form(spec: Dict[str, Any]) -> str:
    """Check a form spec v1 document without storing anything. Returns
    {"valid","errors":[{"path","message"}],"warnings","compliance"}; paths
    are JSON pointers into the document. The organisation's compliance rules
    need an AI review and are not checked here. At most 1 MB, 200 pages and
    2000 fields."""
    await _key("forms:read")
    if len(json.dumps(spec)) > MAX_DOCUMENT_BYTES:
        await _audit("validate_form", False, "document too large")
        raise ValueError(DOCUMENT_TOO_LARGE)
    result = await run_in_threadpool(check_spec_document, spec)
    await _audit("validate_form", result["valid"], f"{len(result['errors'])} errors")
    return json.dumps(result)


@mcp.tool()
async def dry_run_ops(
    form_id: str, ops: List[Dict[str, Any]], atomic: bool = False
) -> str:
    """Preview update_form: apply the same ops to a copy of the form and
    return {"ok","applied","atomic","form" (the resulting spec document),
    "diff" (pages and fields added, removed, moved, changed, with paths),
    "results"}. Nothing is stored. Op shapes: see update_form
    (at most 200 ops)."""
    key = await _key("forms:write")
    workspace_forms = await _workspace_form_ids(key.workspace_id)
    _require_form_in_workspace(form_id, workspace_forms)
    service = _c().form_spec_service()
    form, settings = await service.load(key.workspace_id, form_id)
    try:
        preview = await service.preview_async(form, settings, ops, atomic)
    except HTTPException as e:
        await _audit("dry_run_ops", False, form_id)
        raise ValueError(_error_text(e)) from e
    await _audit(
        "dry_run_ops", preview.ok, f"{form_id}: {len(preview.results)} ops (dry run)"
    )
    return json.dumps(preview.model_dump(mode="json", by_alias=True))


def _error_text(error: HTTPException) -> str:
    """An HTTPException's message (and located errors) in words."""
    content = error.content
    if isinstance(content, dict):
        details = "; ".join(
            f"{e.get('path') or '/'}: {e.get('message')}"
            for e in content.get("errors") or []
        )
        message = str(content.get("message") or "")
        return message + (f" ({details})" if details else "")
    return str(content)


# What a refused publish tells the caller: at most this many problems, each
# at most this many characters.
MAX_PUBLISH_PROBLEMS = 20
MAX_PUBLISH_PROBLEM_CHARS = 500
MAX_PUBLISH_FIELD_ID_CHARS = 64


def _one_line(value: Any, limit: int) -> str:
    """``value`` as one plain line of at most ``limit`` characters: control
    and format characters (newlines, ESC and ANSI sequences, bidi overrides,
    zero-width and tag characters) are dropped, other whitespace becomes a
    single space. The text goes to an agent: a question id or title an editor
    wrote must not be able to start a line of its own."""
    text = "".join(
        char
        for char in str(value if value is not None else "")
        if char.isspace() or unicodedata.category(char) not in ("Cc", "Cf")
    )
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 3] + "..."


def _publish_refusal_text(error: HTTPException) -> Optional[str]:
    """Why a publish was refused, one problem per line as ``code: message``
    (``code (field "<id>"): message`` when the problem belongs to a question),
    in the server's order. Only the code, the question id and the message of
    each problem: nothing else of the refusal (no report id or content).
    None unless this is the 422 ``form_not_publishable`` refusal."""
    content = error.content
    if not isinstance(content, dict) or content.get("code") != FORM_NOT_PUBLISHABLE:
        return None
    problems = [p for p in content.get("problems") or [] if isinstance(p, dict)]
    lines = []
    for problem in problems[:MAX_PUBLISH_PROBLEMS]:
        code = _one_line(problem.get("code"), 64) or "problem"
        field_id = _one_line(
            problem.get("fieldId"), MAX_PUBLISH_FIELD_ID_CHARS
        ).replace('"', "'")
        where = f' (field "{field_id}")' if field_id else ""
        message = _one_line(problem.get("message"), MAX_PUBLISH_PROBLEM_CHARS)
        line = f"{code}{where}: {message}"
        if len(line) > MAX_PUBLISH_PROBLEM_CHARS:
            line = line[: MAX_PUBLISH_PROBLEM_CHARS - 3] + "..."
        lines.append(line)
    if len(problems) > MAX_PUBLISH_PROBLEMS:
        lines.append(f"and {len(problems) - MAX_PUBLISH_PROBLEMS} more")
    return "\n".join(["This form can't be published yet:", *lines])


@mcp.tool()
async def publish_form(form_id: str) -> str:
    """Publish a form so it can accept responses. Returns the share slug."""
    key = await _key("forms:write")
    from backend.app.container import container

    workspace_forms = await _workspace_form_ids(key.workspace_id)
    _require_form_in_workspace(form_id, workspace_forms)
    try:
        await container.workspace_form_service().publish_form(
            workspace_id=key.workspace_id,
            form_id=RecordId(form_id),
            user=_acting_user(key),
        )
    except HTTPException as e:
        reasons = _publish_refusal_text(e)
        if reasons is None:
            # any other refusal (403, 404, 410, ...) is answered as before
            raise
        raise ValueError(reasons) from e
    refreshed = (
        await _c().workspace_form_repo().find_workspace_form(key.workspace_id, form_id)
    )
    slug = refreshed.settings.custom_url if refreshed and refreshed.settings else None
    await _audit("publish_form", True, form_id)
    return json.dumps({"formId": form_id, "published": True, "slug": slug})


@mcp.tool()
async def list_responses(form_id: str, limit: int = 20) -> str:
    """List a form's responses (most recent first): response id, submission
    time, answer count and any deletion request's status. Use get_response
    for full answers."""
    key = await _key("responses:read")
    workspace_forms = await _workspace_form_ids(key.workspace_id)
    _require_form_in_workspace(form_id, workspace_forms)
    # this workspace's responses only (#768)
    items, _ = await list_response_summaries(key.workspace_id, form_id, limit)
    await _audit("list_responses", True, f"{form_id}: {len(items)}")
    return json.dumps(items)


@mcp.tool()
async def get_response(response_id: str) -> str:
    """Get one response's full answers."""
    key = await _key("responses:read")
    # this workspace's copy (#768), decrypted on this read path only (the
    # same rule as the dashboard's response views)
    detail = await response_detail(key.workspace_id, response_id)
    if detail is None:
        raise ValueError("Response not found in this workspace.")
    await _audit("get_response", True, response_id)
    return json.dumps(detail)


@mcp.tool()
async def list_deletion_requests() -> str:
    """List pending response-deletion requests across the workspace — the
    privacy queue an operator (or agent) should act on."""
    key = await _key("deletion_requests:read")
    workspace_forms = await _workspace_form_ids(key.workspace_id)
    scope = await response_scope(
        _c().workspace_form_repo(), key.workspace_id, list(workspace_forms)
    )
    requests = (
        await _c().form_response_repo().list_deletion_requests_for_form_ids(scope)
    )
    items = [
        {
            "responseId": r.response_id,
            "formId": r.form_id,
            "status": getattr(r, "status", None),
            "requestedAt": str(getattr(r, "created_at", "")),
        }
        for r in requests
    ]
    await _audit("list_deletion_requests", True, f"{len(items)} requests")
    return json.dumps(items)


@mcp.tool()
async def get_ai_profile() -> str:
    """The workspace's AI profile: about, form guidelines and compliance
    requirements. Respect these when creating or editing forms."""
    key = await _key("forms:read")
    profile = await AIProfileService.get_profile_for_prompt(key.workspace_id)
    await _audit("get_ai_profile", True)
    return json.dumps(
        {
            "about": profile.about if profile else "",
            "guidelines": profile.guidelines if profile else "",
            "compliance": profile.compliance if profile else "",
        }
    )


class MCPAuthMiddleware:
    """Bearer API key → contextvar; anything else is a clean 401."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}
        auth = headers.get("authorization", "")
        token = auth[7:].strip() if auth.lower().startswith("bearer ") else ""
        try:
            key = await APIKeyService.authenticate(token)
        except HTTPException:
            body = json.dumps(
                {"error": "Provide a valid workspace API key as a Bearer token."}
            ).encode()
            await send(
                {
                    "type": "http.response.start",
                    "status": 401,
                    "headers": [
                        (b"content-type", b"application/json"),
                        (b"content-length", str(len(body)).encode()),
                    ],
                }
            )
            await send({"type": "http.response.body", "body": body})
            return
        ctx_token = current_api_key.set(key)
        try:
            await self.app(scope, receive, send)
        finally:
            current_api_key.reset(ctx_token)


@functools.cache
def _streamable_http_app():
    # Built once: each build makes a new session manager, and the app's
    # lifespan runs the one ``mcp.session_manager`` returns.
    return mcp.streamable_http_app(
        stateless_http=True,
        streamable_http_path="/",
        # Host pinning (DNS-rebinding protection) is for unauthenticated
        # localhost servers; this endpoint requires a Bearer API key and is
        # deployed under arbitrary hostnames, so the Host allowlist can't be
        # known here.
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=False
        ),
    )


def build_mcp_asgi_app():
    """The auth-wrapped MCP ASGI app, ready to mount at /mcp."""
    return MCPAuthMiddleware(_streamable_http_app())
