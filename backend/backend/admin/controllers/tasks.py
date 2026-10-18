"""The portal's task pages: list, start, history, progress, cancel, resume.

Every route is ``Level.SECOND_FACTOR`` and goes through the default-deny registry.

How a change is protected (the same prepare/confirm shape any other
state-changing portal page can use):

* A dry run changes nothing: it needs the session, CSRF, and is audited and
  rate limited per admin.
* Apply, cancel and resume carry an ``ActionBound`` single-use step-up token.
  The pages obtain it without JavaScript through ``POST /tasks/prepare``
  (``stepup_exempt``: it verifies a fresh factor code itself, exactly as
  ``POST /api/stepup`` does, and only issues a token). The confirmation page it
  renders holds the token; the final route consumes it. The token is bound to
  ``hash(action, ...)`` with the task, its version and the canonical params hash
  (apply, ``dry_run=false``), the run id (cancel), or the run id and its params
  hash (resume), so it cannot be replayed for anything else.

Parameters travel only in POST bodies; no URL, log line or audit field carries a
submitted value that did not pass validation against the task's own ``Params``.
Every refusal is one of a fixed set of sentences.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional

from fastapi import BackgroundTasks, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response

from backend.admin.controllers.pages import _page
from backend.admin.controllers.portal import _ip, _portal, _rid, _schedule, _ua
from backend.admin.gate.levels import Level, RouteRegistry
from backend.admin.gate.stepup import ActionBound
from backend.admin.security.ratelimit import Rule
from backend.admin.services import factors as fsvc
from backend.admin.services import taskform
from backend.admin.services import task_pages as tp
from backend.admin.services.stepup import action_hash
from backend.admin.tasks import signing
from backend.admin.tasks.spec import RunState

DRY_RUN_RULE = Rule("task_dry_run", 10, 300)  # per admin
INVALID = "invalid"  # a binding no issued token can match
MAX_CODE = 40
NOTICES_OK = frozenset({"started", "cancel_requested", "cancel_again", "resume_started"})
PAGE_MAX = 1000

APPLY_ACTION = "tasks.apply"
CANCEL_ACTION = "tasks.cancel"
RESUME_ACTION = "tasks.resume"


def _session(request: Request):
    return request.scope["state"]["session"]


async def _form(request: Request) -> dict[str, str]:
    """The posted fields that are plain text (files and repeats are ignored)."""
    form = await request.form()
    return {k: v for k, v in form.items() if isinstance(v, str)}


def _int(value: Optional[str], default: int = 0, high: int = PAGE_MAX) -> int:
    if value is None or not value.isascii() or not value.isdigit() or len(value) > 9:
        return default
    return min(int(value), high)


def apply_binding(meta, params: Mapping[str, Any]) -> list:
    """What an apply token is bound to: task, version, canonical params hash and
    ``dry_run=false`` (a dry run never needs a token)."""
    return [meta.name, meta.version, signing.params_hash(dict(params)), "dry_run=false"]


async def _apply_parts(request: Request) -> list:
    portal = _portal(request)
    meta = portal.tasks.meta(request.path_params.get("name", ""))
    if meta is None or not meta.mutating:
        return [INVALID]
    parsed = taskform.parse(meta, taskform.fields_for(meta), await _form(request))
    return apply_binding(meta, parsed.params) if parsed.params is not None else [INVALID]


async def _cancel_parts(request: Request) -> list:
    run_id = _portal(request).tasks.parse_id(request.path_params.get("run_id", ""))
    return [str(run_id)] if run_id else [INVALID]


async def _resume_parts(request: Request) -> list:
    portal = _portal(request)
    run_id = portal.tasks.parse_id(request.path_params.get("run_id", ""))
    target = await portal.tasks.resume_target(run_id) if run_id else None
    return [str(run_id), target[1]] if run_id and target else [INVALID]


APPLY = ActionBound(APPLY_ACTION, _apply_parts)
CANCEL = ActionBound(CANCEL_ACTION, _cancel_parts)
RESUME = ActionBound(RESUME_ACTION, _resume_parts)


def _posted_values(fields, form: Mapping[str, str], bad) -> dict:
    """Form values to show again after an error: only fields that were fine
    (a rejected field goes back to its default, so no rejected text is echoed)."""
    values = taskform.form_values(fields, {})
    if "?" in bad:
        return values
    for f in fields:
        if not f.supported or f.name in bad:
            continue
        if f.kind == "bool":
            values[f.input_name] = f.input_name in form
        elif f.kind == "multi":
            for c in f.choices:
                values[f.choice_name(c)] = f.choice_name(c) in form
        elif isinstance(form.get(f.input_name), str):
            values[f.input_name] = form[f.input_name][: taskform.MAX_LINES_TEXT]
    return values


def _hidden(fields, params: Mapping[str, Any]) -> list[tuple[str, str]]:
    out = []
    for name, value in taskform.form_values(fields, params).items():
        if value is True:
            out.append((name, "on"))
        elif value is not False:
            out.append((name, value))
    return out


def register(reg: RouteRegistry) -> None:
    async def task_page(
        request: Request, meta, status: int = 200, *, values=None, bad=(), notice=None, **extra
    ):
        portal = _portal(request)
        fields = taskform.fields_for(meta)
        return await _page(
            request, "task.html", "tasks", status,
            meta=meta, fields=fields, can_submit=taskform.can_submit(fields),
            values=values if values is not None else taskform.form_values(fields, {}),
            bad=sorted(bad), notice=notice, last_dry=await portal.tasks.last_dry_run(meta),
            retry_minutes=extra.pop("retry_minutes", 0), **extra,
        )

    async def run_page(request: Request, run_id, status: int = 200, notice=None):
        portal = _portal(request)
        detail = await portal.tasks.run_detail(run_id, _int(request.query_params.get("after")))
        if detail is None:
            return Response(status_code=404)
        return await _page(
            request, "run.html", "tasks", status, d=detail, notice=notice,
        )

    # -- reads (literal paths first: ``/tasks/{name}`` would swallow them) -------------
    @reg.route("/tasks", level=Level.SECOND_FACTOR)
    async def tasks_list(request: Request):
        rows = await _portal(request).tasks.task_rows()
        return await _page(request, "tasks.html", "tasks", rows=rows)

    @reg.route("/tasks/runs", level=Level.SECOND_FACTOR)
    async def runs_history(request: Request):
        portal = _portal(request)
        task = request.query_params.get("task") or ""
        state = request.query_params.get("state") or ""
        names = [m.name for m in portal.tasks.metas()]
        states = [s.value for s in RunState]
        if (task and task not in names) or (state and state not in states):
            return await _page(
                request, "runs.html", "tasks", 400, page=None, task="", state="", names=names,
                states=states, error="task" if task and task not in names else "state",
            )
        page = await portal.tasks.runs_page(
            max(1, _int(request.query_params.get("page"), 1)), task or None, state or None
        )
        return await _page(
            request, "runs.html", "tasks", page=page, task=task, state=state, names=names,
            states=states, error=None,
        )

    @reg.route("/tasks/runs/{run_id}", level=Level.SECOND_FACTOR)
    async def run_detail(request: Request, run_id: str):
        parsed = _portal(request).tasks.parse_id(run_id)
        if parsed is None:
            return Response(status_code=404)
        notice = request.query_params.get("notice")
        return await run_page(request, parsed, notice=notice if notice in NOTICES_OK else None)

    @reg.route("/api/tasks/runs/{run_id}", level=Level.SECOND_FACTOR)
    async def run_progress(request: Request, run_id: str):
        portal = _portal(request)
        parsed = portal.tasks.parse_id(run_id)
        payload = (
            await portal.tasks.run_progress(parsed, _int(request.query_params.get("after")))
            if parsed else None
        )
        if payload is None:
            return JSONResponse({"error": "not_found"}, status_code=404)
        return payload

    @reg.route("/tasks/{name}", level=Level.SECOND_FACTOR)
    async def task_form(request: Request, name: str):
        meta = _portal(request).tasks.meta(name)
        if meta is None:
            return Response(status_code=404)
        return await task_page(request, meta)

    # -- starting ------------------------------------------------------------------------
    async def parsed_or_page(request: Request, meta):
        """``(params, None)`` or ``(None, response)`` for the posted form."""
        form = await _form(request)
        fields = taskform.fields_for(meta)
        parsed = taskform.parse(meta, fields, form)
        if parsed.params is None or not taskform.can_submit(fields):
            return None, await task_page(
                request, meta, 400, values=_posted_values(fields, form, parsed.bad),
                bad=parsed.bad - {"?"}, notice="bad_params",
            )
        return parsed.params, None

    def started_response(request: Request, result: tp.Started, notice: str):
        return RedirectResponse(f"/tasks/runs/{result.run_id}?notice={notice}", status_code=303)

    @reg.route(
        "/tasks/{name}/dry-run", level=Level.SECOND_FACTOR, methods=["POST"],
        stepup_exempt="a dry run (or a read-only task's run) changes no data; it is audited "
        "and rate limited per admin",
    )
    async def start_dry_run(request: Request, name: str):
        portal, session = _portal(request), _session(request)
        meta = portal.tasks.meta(name)
        if meta is None:
            return Response(status_code=404)
        decision = await portal.limiter.hit(DRY_RUN_RULE, portal.limiter.email_key(session.email))
        if not decision.allowed:
            return await task_page(
                request, meta, 429, notice="rate_limited",
                retry_minutes=max(1, decision.retry_after // 60 + 1),
            )
        params, refused = await parsed_or_page(request, meta)
        if refused is not None:
            return refused
        result = await portal.tasks.request_run(
            session, meta, params, True, _ip(request), _ua(request), _rid(request)
        )
        if not result.ok:
            return await task_page(request, meta, 409, notice=result.refusal.value)
        return started_response(request, result, "started")

    @reg.route("/tasks/{name}/apply", level=Level.SECOND_FACTOR, methods=["POST"], stepup=APPLY)
    async def start_apply(request: Request, name: str):
        portal, session = _portal(request), _session(request)
        meta = portal.tasks.meta(name)
        if meta is None or not meta.mutating:
            return Response(status_code=404)
        params, refused = await parsed_or_page(request, meta)
        if refused is not None:
            return refused
        result = await portal.tasks.request_run(
            session, meta, params, False, _ip(request), _ua(request), _rid(request)
        )
        if not result.ok:
            return await task_page(request, meta, 409, notice=result.refusal.value)
        return started_response(request, result, "started")

    # -- cancel and resume ------------------------------------------------------------------
    @reg.route("/tasks/runs/{run_id}/cancel", level=Level.SECOND_FACTOR, methods=["POST"], stepup=CANCEL)
    async def cancel_run(request: Request, run_id: str):
        portal, session = _portal(request), _session(request)
        parsed = portal.tasks.parse_id(run_id)
        if parsed is None:
            return Response(status_code=404)
        result = await portal.tasks.request_cancel(
            session, parsed, _ip(request), _ua(request), _rid(request)
        )
        if result.refusal is tp.Refusal.unknown_run:
            return Response(status_code=404)
        if not result.ok:
            return await run_page(request, parsed, 409, notice=result.refusal.value)
        return RedirectResponse(
            f"/tasks/runs/{parsed}?notice={'cancel_again' if result.already else 'cancel_requested'}",
            status_code=303,
        )

    @reg.route("/tasks/runs/{run_id}/resume", level=Level.SECOND_FACTOR, methods=["POST"], stepup=RESUME)
    async def resume_run(request: Request, run_id: str):
        portal, session = _portal(request), _session(request)
        parsed = portal.tasks.parse_id(run_id)
        if parsed is None:
            return Response(status_code=404)
        result = await portal.tasks.request_resume(
            session, parsed, _ip(request), _ua(request), _rid(request)
        )
        if result.refusal is tp.Refusal.unknown_run:
            return Response(status_code=404)
        if not result.ok:
            return await run_page(request, parsed, 409, notice=result.refusal.value)
        return started_response(request, result, "resume_started")

    # -- the code step (no JavaScript needed) ------------------------------------------------
    @reg.route(
        "/tasks/prepare", level=Level.SECOND_FACTOR, methods=["POST"],
        stepup_exempt="verifies a fresh factor code itself (the same checks and lockouts as "
        "/api/stepup) and only issues a single-use token; it changes no task state",
    )
    async def prepare(request: Request, background: BackgroundTasks):
        portal, session = _portal(request), _session(request)
        form = await _form(request)
        action = form.get("action", "")
        context: dict[str, Any] = {"summary": [], "hidden": [], "heading": "", "back": "/tasks"}
        if action == "apply":
            meta = portal.tasks.meta(form.get("task", ""))
            if meta is None or not meta.mutating:
                return Response(status_code=404)
            params, refused = await parsed_or_page(request, meta)
            if refused is not None:
                return refused
            if meta.requires_prior_dry_run and not await portal.tasks.prior_dry_run_exists(meta, params):
                return await task_page(
                    request, meta, 409, notice="dry_run_required",
                    values=taskform.form_values(taskform.fields_for(meta), params),
                )
            fields = taskform.fields_for(meta)
            name, parts = APPLY_ACTION, apply_binding(meta, params)
            context.update(
                kind="apply", destination=f"/tasks/{meta.name}/apply",
                title=meta.title or meta.name, task=meta.name, version=meta.version,
                summary=taskform.summary(fields, params), hidden=_hidden(fields, params),
                back=f"/tasks/{meta.name}",
            )
        elif action in ("cancel", "resume"):
            run_id = portal.tasks.parse_id(form.get("run_id", ""))
            if run_id is None:
                return Response(status_code=404)
            target = await portal.tasks.resume_target(run_id)
            if target is None:
                return Response(status_code=404)
            if action == "cancel":
                detail = await portal.tasks.run_detail(run_id)
                if detail is not None and detail.run.active and not detail.can_cancel:
                    return await run_page(request, run_id, 200, notice="cancel_again")
                if detail is None or not detail.can_cancel:
                    return await run_page(request, run_id, 409, notice=tp.Refusal.not_active.value)
                name, parts = CANCEL_ACTION, [str(run_id)]
            else:
                blocked = await portal.tasks.check_resume(run_id)
                if blocked is not None:
                    return await run_page(request, run_id, 409, notice=blocked)
                name, parts = RESUME_ACTION, [str(run_id), target[1]]
            context.update(
                kind=action, destination=f"/tasks/runs/{run_id}/{action}", title=target[0],
                task=target[0], version=None, run_id=str(run_id), back=f"/tasks/runs/{run_id}",
            )
        else:
            return Response(status_code=400)

        code = form.get("code", "")[:MAX_CODE].strip()
        failed, locked, token = False, 0, None
        if code:
            outcome = await portal.factors.verify_stepup(
                session, code, _ip(request), _ua(request), _rid(request)
            )
            _schedule(background, outcome.after)
            if outcome.ok:
                fresh = await portal.sessions.reload(session)
                token = portal.stepup.issue(fresh, action_hash(name, *parts)) if fresh else None
                failed = token is None
            else:
                locked = outcome.retry_minutes if outcome.reason in (fsvc.LOCKED, fsvc.PAUSED) else 0
                failed = outcome.reason == fsvc.WRONG
        # the rendered page holds a single-use token for exactly this action
        status = 429 if locked else 200
        response = await _page(
            request, "task_confirm.html", "tasks", status, token=token, failed=failed,
            locked_minutes=locked, **context,
        )
        response.background = background
        return response
