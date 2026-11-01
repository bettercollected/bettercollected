"""Where a question's options come from, and what a respondent may choose.

``OptionSourceService.options`` builds the options of one source (a workspace
list, or the answers given to a question of another form) on the server, from
data a respondent's browser never sees:

- A **list** is read by its revision: one cheap query says whether the cached
  copy is still the list.
- **Another form's answers** are read by a *token* (count, newest change and
  newest id of the eligible responses, one aggregate query): a new, edited,
  deleted, expired or deletion-requested response changes it, so the options are
  rebuilt at once, in every process, and nothing stale is served. Responses
  with a deletion request of any status, and responses submitted with the
  anonymous choice, never count. At most ``ANSWER_OPTIONS_MAX`` distinct
  labels and ``ANSWER_RESPONSES_MAX`` responses are read; the result says when
  it was cut. Labels are deduplicated by their normalised text and get a keyed
  id (``ids.answer_option_id``). One rebuild at a time per source.

``serve`` is the public respondent endpoint's logic: labels only, published
forms only, rate limited. ``apply`` is the submit step: it refuses a chosen
option the source does not offer now and writes the label snapshot every
reader (export, webhook, screen) shows.
"""

import asyncio
import datetime as dt
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from http import HTTPStatus
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Set, Tuple

from bson.errors import InvalidId
from common.clock import utcnow
from common.ids import RecordId
from loguru import logger
from starlette.concurrency import run_in_threadpool

from backend.app.exceptions import HTTPException
from backend.app.services.option_sources import ids, read, text
from backend.app.utils.client_ip import rate_limit_key

OPTION_UNAVAILABLE = "option_unavailable"

# the public options endpoint (constants, not settings: one inventory row)
RATE_LIMIT_SCOPE = "option-sources"
RATE_PER_CLIENT = 120
RATE_PER_FORM = 3_000
RATE_WINDOW_SECONDS = 60
PAGE_DEFAULT = 50
PAGE_MAX = 100
QUERY_MAX = 100
PARENTS_MAX = 50
ID_MAX = 200
FORM_CACHE_SECONDS = 30.0
FORM_CACHE_SIZE = 1024
SOURCE_CACHE_SECONDS = 60.0
SOURCE_CACHE_SIZE = 256
BATCH = 500


@dataclass(frozen=True)
class Option:
    """One option: its id, the label people see, the label folded (for search
    and de-duplication) and, for a list item, its folded group key."""

    id: str
    label: str
    key: str
    group_key: Optional[str] = None


@dataclass
class SourceOptions:
    options: Tuple[Option, ...] = ()
    # False: the list or the form's question is gone (nothing is offered)
    available: bool = True
    # more than the caps allow existed; only the first part is offered
    truncated: bool = False
    # eligible responses behind an answers source (a count, never a value)
    responses: int = 0
    by_id: Dict[str, Option] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.by_id:
            self.by_id = {option.id: option for option in self.options}


GONE = SourceOptions(available=False)


def narrow(
    options: Sequence[Option], parent_keys: Optional[Set[str]]
) -> Tuple[Option, ...]:
    """The options a dependent list offers: those whose group is one of the
    parent's chosen labels, and the ones without a group. ``parent_keys`` None:
    no answer to the parent, nothing is filtered."""
    if parent_keys is None:
        return tuple(options)
    return tuple(
        option
        for option in options
        if option.group_key is None or option.group_key in parent_keys
    )


def search(
    options: Sequence[Option], query: Optional[str], limit: int, offset: int
) -> Tuple[List[Option], int]:
    """A page of the options whose label contains ``query`` (ignoring case)."""
    needle = text.fold(query) if query else ""
    found = [o for o in options if needle in o.key] if needle else list(options)
    return found[offset : offset + limit], len(found)


def _not_found() -> HTTPException:
    return HTTPException(status_code=HTTPStatus.NOT_FOUND, content="Not found")


@dataclass
class _Question:
    source: Dict[str, Any]
    parent_field_id: Optional[str] = None
    # a static parent question's {option id: text}, or its own source
    parent_static: Optional[Dict[str, str]] = None
    parent_source: Optional[Dict[str, Any]] = None


@dataclass
class _Servable:
    form_id: str
    questions: Dict[str, _Question]
    loaded_at: float


@dataclass
class _Cached:
    token: Any
    value: SourceOptions
    at: float


class OptionSourceService:
    def __init__(
        self,
        list_repo,
        form_repo,
        workspace_form_repo,
        response_repo,
        form_response_service,
        rate_limiter,
        authorization_service=None,
        monotonic: Callable[[], float] = time.monotonic,
        now: Callable[[], dt.datetime] = utcnow,
    ):
        self._authorization = authorization_service
        self._lists = list_repo
        self._forms = form_repo
        self._workspace_forms = workspace_form_repo
        self._responses = response_repo
        self._response_service = form_response_service
        self._limiter = rate_limiter
        self._monotonic = monotonic
        self._now = now
        self._servable_cache: Dict[Tuple[str, str], _Servable] = {}
        self._cache: "OrderedDict[Tuple, _Cached]" = OrderedDict()
        self._locks: Dict[Tuple, asyncio.Lock] = {}

    # ------------------------------------------------------------------ options

    async def options(self, workspace_id, source: Mapping[str, Any]) -> SourceOptions:
        """The options of ``source`` (a dict: kind, list_id / form_id,
        question_id) in this workspace, as they are now."""
        kind = source.get("kind")
        if kind == "list":
            return await self._list_options(workspace_id, str(source.get("list_id")))
        if kind == "form_answers":
            return await self._answer_options(
                workspace_id,
                str(source.get("form_id")),
                str(source.get("question_id")),
            )
        return GONE

    def _remember(self, key: Tuple, token: Any, value: SourceOptions) -> None:
        self._cache[key] = _Cached(token, value, self._monotonic())
        self._cache.move_to_end(key)
        while len(self._cache) > SOURCE_CACHE_SIZE:
            dropped, _ = self._cache.popitem(last=False)
            self._locks.pop(dropped, None)

    def _fresh(self, key: Tuple, token: Any) -> Optional[SourceOptions]:
        cached = self._cache.get(key)
        if (
            cached is not None
            and cached.token == token
            and self._monotonic() - cached.at < SOURCE_CACHE_SECONDS
        ):
            self._cache.move_to_end(key)
            return cached.value
        return None

    def forget(self, workspace_id, list_id: str) -> None:
        """A list was written in this process: its cached copy goes."""
        self._cache.pop(("list", str(workspace_id), str(list_id)), None)

    async def _list_options(self, workspace_id, list_id: str) -> SourceOptions:
        revision = await self._lists.revision(workspace_id, list_id)
        if revision is None:
            return GONE
        key = ("list", str(workspace_id), list_id)
        hit = self._fresh(key, revision)
        if hit is not None:
            return hit
        document = await self._lists.get(workspace_id, list_id)
        if document is None:
            return GONE
        value = SourceOptions(options=list_items(document))
        self._remember(key, document.revision, value)
        return value

    async def _answer_options(
        self, workspace_id, form_id: str, question_id: str
    ) -> SourceOptions:
        try:
            scope = await self._response_service.scope(workspace_id, [form_id])
            now_iso = _iso(self._now())
            token = await self._responses.option_source_token(scope, now_iso)
        except Exception as error:  # the source cannot be read: offer nothing
            logger.warning(
                "option sources: a source could not be read ({})",
                type(error).__name__,
            )
            return GONE
        key = ("answers", str(workspace_id), form_id, question_id)
        hit = self._fresh(key, token)
        if hit is not None:
            return hit
        lock = self._locks.setdefault(key, asyncio.Lock())
        async with lock:
            hit = self._fresh(key, token)
            if hit is not None:
                return hit
            value = await self._rebuild(
                workspace_id, form_id, question_id, scope, now_iso, token[0]
            )
            self._remember(key, token, value)
            return value

    async def _rebuild(
        self, workspace_id, form_id, question_id, scope, now_iso, eligible: int
    ) -> SourceOptions:
        if not await self._workspace_forms.check_if_form_exists_in_workspace(
            workspace_id, form_id
        ):
            return GONE
        document = await self._forms.get_form_document_by_id(form_id)
        question = next(
            (
                q
                for q in read.page_questions(document)
                if str(read.get(q, "id")) == question_id
            ),
            None,
        )
        if question is None or answer_question_problem(question) is not None:
            return GONE
        kind = read.field_type(question)
        choice_labels = read.static_labels(question) if kind != "short_text" else {}
        found: Dict[str, str] = {}
        truncated = False
        read_count = 0
        after: Optional[str] = None
        while True:
            batch = await self._responses.option_source_batch(
                scope, now_iso, after_id=after, limit=BATCH
            )
            if not batch:
                break
            after = str(batch[-1].id)
            read_count += len(batch)
            labels = await run_in_threadpool(
                self._labels, workspace_id, batch, question_id, kind, choice_labels
            )
            for label in labels:
                key = text.fold(label)
                if key in found:
                    continue
                if len(found) >= text.ANSWER_OPTIONS_MAX:
                    truncated = True
                    break
                found[key] = label
            if truncated or len(batch) < BATCH:
                break
            if read_count >= text.ANSWER_RESPONSES_MAX:
                truncated = True
                break
        options = tuple(
            Option(
                id=ids.answer_option_id(workspace_id, form_id, question_id, key),
                label=found[key],
                key=key,
            )
            for key in sorted(found)
        )
        logger.info(
            "option sources: built {} option(s) from {} response(s){}",
            len(options),
            read_count,
            " (cut)" if truncated else "",
        )
        return SourceOptions(options=options, truncated=truncated, responses=eligible)

    def _labels(
        self, workspace_id, batch, question_id: str, kind: str, choice_labels
    ) -> List[str]:
        """The labels one batch of responses gives (off the event loop)."""
        found: List[str] = []
        for response in batch:
            if response.answers is None:
                continue
            decrypted = self._response_service.decrypt_form_response(
                workspace_id=workspace_id, response=response
            )
            answers = decrypted.answers if isinstance(decrypted.answers, dict) else {}
            raw = answers.get(question_id)
            if hasattr(raw, "model_dump"):
                raw = raw.model_dump(exclude_none=True)
            if not isinstance(raw, dict):
                continue
            if kind == "short_text":
                candidates = [raw.get("text")]
            else:
                chosen: List[Any] = []
                single = raw.get("choice")
                multiple = raw.get("choices")
                if isinstance(single, dict):
                    chosen.append(single.get("value"))
                if isinstance(multiple, dict):
                    values = multiple.get("values")
                    chosen.extend(values if isinstance(values, list) else [])
                candidates = [
                    choice_labels.get(c) for c in chosen if isinstance(c, str)
                ]
            for candidate in candidates:
                label = text.clean(candidate, text.LABEL_MAX)
                if label is not None:
                    found.append(label)
        return found

    # ------------------------------------------------------------- save checks

    async def authorize_source(
        self,
        workspace_id,
        source: Mapping[str, Any],
        user,
        own_form_id: Optional[str] = None,
    ) -> None:
        """May ``user`` point a question at ``source``? The list must be one of
        this workspace; another form's answers must come from a form of this
        workspace (not the form itself) and the user must hold
        ``response.read`` on it, and the question must be one that can be a
        source. The same 422 for a missing and a foreign list or form."""
        from backend.app.models.enum.permission import Permission
        from backend.app.services.option_sources.checks import (
            FORBIDDEN_CODE,
            INVALID_CODE,
        )

        def invalid(message: str) -> HTTPException:
            return HTTPException(
                status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
                content={"code": INVALID_CODE, "message": message},
            )

        if source.get("kind") == "list":
            if (
                await self._lists.revision(workspace_id, str(source.get("list_id")))
                is None
            ):
                raise invalid("That list does not exist in this workspace.")
            return
        if getattr(user, "auth_method", None) == "api_key":
            # a key's scope says what its holder may read, not the creator who
            # may point a form at another form's answers: that is set by a person
            # in the builder (or the spec API as a signed-in user), never by a key
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN,
                content={
                    "code": FORBIDDEN_CODE,
                    "message": "Options from another form's answers are set in the "
                    "form builder, not with an API key.",
                },
            )
        form_id = str(source.get("form_id"))
        if own_form_id is not None and form_id == str(own_form_id):
            raise invalid("A form cannot take its options from its own answers.")
        if not await self._workspace_forms.check_if_form_exists_in_workspace(
            workspace_id, form_id
        ):
            raise invalid("That form does not exist in this workspace.")
        if not await self._authorization.has_permission(
            user, Permission.RESPONSE_READ, workspace_id, form_id=form_id
        ):
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN,
                content={
                    "code": FORBIDDEN_CODE,
                    "message": "You need permission to read that form's responses "
                    "to use its answers as options.",
                },
            )
        document = await self._forms.get_form_document_by_id(form_id)
        question = next(
            (
                q
                for q in read.page_questions(document)
                if str(read.get(q, "id")) == str(source.get("question_id"))
            ),
            None,
        )
        if question is None:
            raise invalid("That question does not exist in that form.")
        problem = answer_question_problem(question)
        if problem is not None:
            raise invalid(f"The answers to {problem} cannot be used as options.")

    async def ensure_resolved(
        self, workspace_id, form: Any, existing: Any, user, own_form_id=None
    ) -> None:
        """For every source the form brings new or changed (against
        ``existing``): the saver may point a question at it
        (``authorize_source``). Sources stored as they are are not asked again."""
        from backend.app.services.option_sources.checks import new_or_changed

        changed = set(new_or_changed(form, existing))
        if not changed:
            return
        for question, source in read.sourced_questions(form):
            if str(read.get(question, "id")) in changed:
                await self.authorize_source(workspace_id, source, user, own_form_id)

    # ------------------------------------------------------------ respondent API

    async def _servable(
        self, workspace_id, form_ref: str, fresh: bool = False
    ) -> Optional[_Servable]:
        key = (str(workspace_id), form_ref)
        cached = self._servable_cache.get(key)
        now = self._monotonic()
        if (
            cached is not None
            and not fresh
            and now - cached.loaded_at < FORM_CACHE_SECONDS
        ):
            return cached
        self._servable_cache.pop(key, None)
        loaded = await self._load_servable(workspace_id, form_ref, now)
        if loaded is not None:
            if len(self._servable_cache) >= FORM_CACHE_SIZE:
                self._servable_cache.clear()
            self._servable_cache[key] = loaded
        return loaded

    async def _load_servable(
        self, workspace_id, form_ref: str, now: float
    ) -> Optional[_Servable]:
        link = await self._workspace_forms.get_workspace_form_with_custom_slug_form_id(
            workspace_id=workspace_id, custom_url=form_ref
        )
        if link is None:
            return None
        try:
            form_id = RecordId(link.form_id)
        except (InvalidId, TypeError, ValueError):
            return None
        published = await self._forms.get_latest_version_of_form(form_id)
        if published is None:
            return None
        by_id = {str(read.get(q, "id")): q for q in read.page_questions(published)}
        questions: Dict[str, _Question] = {}
        for question_id, question in by_id.items():
            source = read.source_dict(question)
            if source is None:
                continue
            info = _Question(
                source=source, parent_field_id=source.get("parent_field_id")
            )
            parent = (
                by_id.get(str(info.parent_field_id)) if info.parent_field_id else None
            )
            if parent is not None:
                parent_source = read.source_dict(parent)
                if parent_source is not None:
                    info.parent_source = parent_source
                else:
                    info.parent_static = read.static_labels(parent)
            questions[question_id] = info
        return _Servable(form_id=str(link.form_id), questions=questions, loaded_at=now)

    async def serve(
        self,
        workspace_id,
        form_ref: str,
        field_id: str,
        query: Optional[str],
        limit: int,
        offset: int,
        parent_ids: Sequence[str],
        client: Optional[str],
    ) -> Dict[str, Any]:
        """One page of the labels a respondent may choose from (``{id,
        label}`` only). 404 (the same) unless the form is published in the
        workspace and has this sourced question."""
        if len(form_ref) > 64 or len(field_id) > ID_MAX:
            raise _not_found()
        servable = await self._servable(workspace_id, form_ref)
        info = servable.questions.get(field_id) if servable else None
        if servable is None or info is None:
            raise _not_found()
        await self._limit(servable.form_id, client)
        return await self._page(
            workspace_id, info, query, limit, offset, list(parent_ids)
        )

    async def _limit(self, form_id: str, client: Optional[str]) -> None:
        for scope_key, limit in (
            (f"{form_id}\n{rate_limit_key(client)}", RATE_PER_CLIENT),
            (f"{form_id}\n*", RATE_PER_FORM),
        ):
            verdict = await self._limiter.hit(
                RATE_LIMIT_SCOPE, scope_key, limit, RATE_WINDOW_SECONDS
            )
            if not verdict.allowed:
                raise HTTPException(
                    status_code=HTTPStatus.TOO_MANY_REQUESTS,
                    content="Too many requests; try again later.",
                    headers={"Retry-After": str(verdict.retry_after)},
                )

    async def _page(
        self,
        workspace_id,
        info: _Question,
        query: Optional[str],
        limit: int,
        offset: int,
        parent_ids: Sequence[str],
    ) -> Dict[str, Any]:
        limit = max(1, min(int(limit), PAGE_MAX))
        offset = max(0, int(offset))
        offered = await self.options(workspace_id, info.source)
        if not offered.available:
            return {"items": [], "total": 0, "truncated": False, "available": False}
        parent_keys = await self._parent_keys(workspace_id, info, parent_ids)
        pool = narrow(offered.options, parent_keys)
        items, total = search(pool, (query or "")[:QUERY_MAX], limit, offset)
        return {
            "items": [{"id": o.id, "label": o.label} for o in items],
            "total": total,
            "truncated": offered.truncated,
            "available": True,
        }

    async def _parent_keys(
        self, workspace_id, info: _Question, parent_ids: Sequence[str]
    ) -> Optional[Set[str]]:
        """The folded labels of the parent options the respondent chose; None
        when the question has no parent or the parent has no answer."""
        chosen = [
            p
            for p in parent_ids[:PARENTS_MAX]
            if isinstance(p, str) and len(p) <= ID_MAX
        ]
        if not info.parent_field_id or not chosen:
            return None
        if info.parent_static is not None:
            labels = info.parent_static
        elif info.parent_source is not None:
            labels = {
                option_id: option.label
                for option_id, option in (
                    await self.options(workspace_id, info.parent_source)
                ).by_id.items()
            }
        else:
            return set()
        return {text.fold(labels[c]) for c in chosen if c in labels}

    async def preview(
        self,
        workspace_id,
        source: Mapping[str, Any],
        parent_labels: Sequence[str],
        query: Optional[str],
        limit: int,
        offset: int,
    ) -> Dict[str, Any]:
        """The builder's view of a source (the caller was authorised): the
        same page as a respondent gets, plus the counts."""
        offered = await self.options(workspace_id, source)
        if not offered.available:
            return {
                "items": [],
                "total": 0,
                "options": 0,
                "responses": 0,
                "truncated": False,
                "available": False,
            }
        keys = {text.fold(label) for label in parent_labels if isinstance(label, str)}
        pool = narrow(offered.options, keys or None)
        limit = max(1, min(int(limit), PAGE_MAX))
        items, total = search(
            pool, (query or "")[:QUERY_MAX], limit, max(0, int(offset))
        )
        return {
            "items": [{"id": o.id, "label": o.label} for o in items],
            "total": total,
            "options": len(offered.options),
            "responses": offered.responses,
            "truncated": offered.truncated,
            "available": True,
        }

    # -------------------------------------------------------------- submit step

    async def apply(
        self,
        workspace_id,
        form: Any,
        answers: Any,
        previous: Optional[Mapping[str, Any]] = None,
        context: Optional[Mapping[str, Any]] = None,
        enforce: Optional[bool] = None,
    ) -> Any:
        """The submit (and respondent edit) step for option sources.

        For each answer to a question with a source: every chosen option that
        is new (all of them on a submission; on an edit those the stored
        answer did not hold) must be offered now (the source, narrowed by the
        parent's answer), else the answer is refused, 422
        ``invalid_answers`` / ``option_unavailable``. The label snapshot is
        written by the server next to the chosen id, whatever a client sent;
        an option kept from the stored answer keeps its stored label and is
        not checked again. A label slot on a question without a source is
        removed. ``context``: all the answers after the edit (visibility and
        the parent's answer); the answers handed in when None."""
        if not isinstance(answers, dict):
            return answers
        sourced = {
            str(read.get(q, "id")): (q, source)
            for q, source in read.sourced_questions(form)
        }
        out = dict(answers)
        # a label slot a client sent for a question with no source is never kept
        for key, value in list(out.items()):
            if key in sourced:
                continue
            cleaned = _without_labels(value)
            if cleaned is not value:
                out[key] = cleaned
        if not sourced:
            return out
        plain_context = {
            str(k): _plain(v)
            for k, v in dict(context if context is not None else out).items()
        }
        shown = _shown_questions(form, plain_context)
        previous = previous or {}
        problems: List[Any] = []
        for question in read.page_questions(form):
            question_id = str(read.get(question, "id"))
            if question_id not in sourced:
                continue
            _, source = sourced[question_id]
            answer = _plain(out.get(question_id)) if question_id in out else None
            chosen = chosen_ids(answer)
            if question_id not in out or not chosen:
                if question_id in out and isinstance(answer, dict):
                    out[question_id] = _with_labels(answer, {})
                continue
            earlier = chosen_ids(_plain(previous.get(question_id)))
            earlier_labels = snapshot_labels(_plain(previous.get(question_id)))
            new = [c for c in chosen if c not in earlier]
            labels: Dict[str, str] = {
                c: earlier_labels[c]
                for c in chosen
                if c in earlier and c in earlier_labels
            }
            offered = await self.options(workspace_id, source)
            by_id = offered.by_id
            if new:
                parent_keys = await self._parent_keys_from_answers(
                    workspace_id, form, source, plain_context
                )
                allowed = {o.id for o in narrow(offered.options, parent_keys)}
                refused = [c for c in new if c not in allowed]
                if refused and question_id in shown:
                    problems.append(_problem(question_id))
                for c in new:
                    if c in by_id and (c in allowed or question_id not in shown):
                        labels[c] = by_id[c].label
            out[question_id] = _with_labels(answer, labels)
        if problems:
            self._refuse(problems, enforce)
        return out

    async def _parent_keys_from_answers(
        self, workspace_id, form, source, answers: Mapping[str, Any]
    ) -> Optional[Set[str]]:
        parent_id = source.get("parent_field_id")
        if not parent_id:
            return None
        chosen = chosen_ids(answers.get(str(parent_id)))
        if not chosen:
            return None
        parent = next(
            (
                q
                for q in read.page_questions(form)
                if str(read.get(q, "id")) == str(parent_id)
            ),
            None,
        )
        if parent is None:
            return set()
        parent_source = read.source_dict(parent)
        if parent_source is not None:
            labels = {
                i: o.label
                for i, o in (
                    await self.options(workspace_id, parent_source)
                ).by_id.items()
            }
            # a stored label of the parent's own answer covers an option that
            # has since gone
            labels = {**snapshot_labels(answers.get(str(parent_id))), **labels}
        else:
            labels = read.static_labels(parent)
        return {text.fold(labels[c]) for c in chosen if c in labels}

    @staticmethod
    def _refuse(problems: List[Any], enforce: Optional[bool]) -> None:
        from backend.app.services.answer_validation import ERROR_CODE, ERROR_MESSAGE

        if enforce is None:
            from backend.config import settings

            enforce = settings.RESPONSE_VALIDATION_ENFORCE
        logger.info(
            "option sources: refused {} answer(s) with an option that is not offered",
            len(problems),
        )
        if not enforce:
            return
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            content={
                "code": ERROR_CODE,
                "message": ERROR_MESSAGE,
                "errors": [problem.as_json() for problem in problems],
            },
        )


# ------------------------------------------------------------------ helpers


def _iso(moment: dt.datetime) -> str:
    moment = moment.astimezone(dt.timezone.utc).replace(tzinfo=None)
    return moment.strftime("%Y-%m-%dT%H:%M:%S.") + f"{moment.microsecond // 1000:03d}Z"


def _problem(field_id: str):
    from backend.app.services.answer_validation import AnswerProblem

    return AnswerProblem(field_id, OPTION_UNAVAILABLE, None, field_id)


def _plain(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json", exclude_none=True)
    return value


def list_items(document) -> Tuple[Option, ...]:
    """A list's items in the order respondents get them."""
    items = list(document.items)
    if document.order == "alphabetical":
        items = sorted(items, key=lambda i: text.fold(i.label))
    return tuple(
        Option(
            id=item.id,
            label=item.label,
            key=text.fold(item.label),
            group_key=text.fold(item.group) if item.group else None,
        )
        for item in items
    )


def chosen_ids(answer: Any) -> List[str]:
    """The option ids a choice answer holds (a dict), in order."""
    if not isinstance(answer, dict):
        return []
    found: List[str] = []
    single = answer.get("choice")
    if (
        isinstance(single, dict)
        and isinstance(single.get("value"), str)
        and single["value"]
    ):
        found.append(single["value"])
    multiple = answer.get("choices")
    if isinstance(multiple, dict) and isinstance(multiple.get("values"), list):
        found.extend(v for v in multiple["values"] if isinstance(v, str) and v)
    return found


def snapshot_labels(answer: Any) -> Dict[str, str]:
    """``{option id: label}`` a stored answer carries."""
    if not isinstance(answer, dict):
        return {}
    found: Dict[str, str] = {}
    single = answer.get("choice")
    if isinstance(single, dict) and isinstance(single.get("value"), str):
        label = single.get("label")
        if isinstance(label, str) and label:
            found[single["value"]] = label
    multiple = answer.get("choices")
    if isinstance(multiple, dict) and isinstance(multiple.get("labels"), dict):
        for option_id, label in multiple["labels"].items():
            if isinstance(option_id, str) and isinstance(label, str) and label:
                found[option_id] = label
    return found


def _with_labels(answer: Any, labels: Mapping[str, str]) -> Any:
    """The answer with the snapshot of ``labels`` for the ids it chose (the
    old snapshot is replaced)."""
    if not isinstance(answer, dict):
        return answer
    new = dict(answer)
    single = new.get("choice")
    if isinstance(single, dict):
        single = dict(single)
        label = labels.get(single.get("value"))
        if label:
            single["label"] = label
        else:
            single.pop("label", None)
        new["choice"] = single
    multiple = new.get("choices")
    if isinstance(multiple, dict):
        multiple = dict(multiple)
        values = (
            multiple.get("values") if isinstance(multiple.get("values"), list) else []
        )
        kept = {v: labels[v] for v in values if isinstance(v, str) and v in labels}
        if kept:
            multiple["labels"] = kept
        else:
            multiple.pop("labels", None)
        new["choices"] = multiple
    return new


def _without_labels(answer: Any) -> Any:
    """The answer without a label slot (same object when it has none)."""
    plain = _plain(answer)
    if not isinstance(plain, dict):
        return answer
    single, multiple = plain.get("choice"), plain.get("choices")
    has = (isinstance(single, dict) and "label" in single) or (
        isinstance(multiple, dict) and "labels" in multiple
    )
    if not has:
        return answer
    new = dict(plain)
    if isinstance(single, dict):
        new["choice"] = {k: v for k, v in single.items() if k != "label"}
    if isinstance(multiple, dict):
        new["choices"] = {k: v for k, v in multiple.items() if k != "labels"}
    return new


def _shown_questions(form: Any, answers: Mapping[str, Any]) -> Set[str]:
    """The ids of the questions this respondent's path shows: on a visited
    page and not hidden by logic (the questions the answer check enforces)."""
    from backend.app.services.answer_validation import (
        _children,
        _counts,
        _slides,
        visited_slides,
    )
    from backend.app.services.repeating_groups import is_hidden_by_logic, logic_sources

    slides = _slides(form)
    if slides is None:
        return {str(read.get(q, "id")) for q in read.page_questions(form)}
    sources = logic_sources(slides)
    shown: Set[str] = set()
    for slide in visited_slides(slides, dict(answers)):
        for question in _children(slide):
            if _counts(question) and not is_hidden_by_logic(
                question, dict(answers), sources
            ):
                shown.add(str(question.id))
    return shown


def answer_question_problem(question: Any) -> Optional[str]:
    """Why a question of another form cannot be a source of options (None
    when it can): only text, dropdown and multiple choice questions, never an
    internal one, one with its own source, or an answer that identifies
    someone (email, phone, address, file ...)."""
    if read.get(question, "internal"):
        return "an internal question"
    kind = read.field_type(question)
    if kind not in read.ANSWER_SOURCE_TYPES:
        return f"a {kind} question"
    if read.has_source(question):
        return "a question whose options come from a source"
    return None
