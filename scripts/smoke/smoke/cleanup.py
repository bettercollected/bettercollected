"""Deleting the forms the suite created, and the one-off cleanup of old ones.

Two things live here (docs/smoke-test.md):

* ``delete_forms``: what every run does at the end, in a ``finally``. It
  deletes exactly the forms whose ids the run was given at creation, through
  the public API's delete (scope ``forms:delete``). A key without that scope is
  not a failed run: the result says so, and ``describe`` turns it into a
  warning that names the scope and lists the ids left behind.

* ``python -m smoke.cleanup``: the optional one-off for forms that earlier runs
  left behind. A dry run unless ``--delete`` is given. A form is a candidate
  only when it carries both markers every run form is created with (the exact
  title shape of ``forms.run_title`` and the exact ``forms.PURPOSE`` text, read
  from the stored form), it is not the standing set, and nothing has touched
  it for ``--min-age-minutes`` (so a run in progress is never hit). It needs
  only SMOKE_API_KEY, SMOKE_WORKSPACE_ID and the API address (SMOKE_APP_URL or
  --api-url): no mailbox, no browser.
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import sys
from dataclasses import dataclass, field
from typing import Callable, List, Mapping, Optional, Sequence, Tuple
from urllib.parse import quote, urlsplit

from smoke import forms
from smoke.config import HANDLE, OBJECT_ID, ConfigError, normalize_url
from smoke.http import Http, HttpError
from smoke.redact import Redactor

DELETE_SCOPE = "forms:delete"
MISSING_SCOPE_CODE = "missing_scope"
CREATOR_LACKS_CODE = "key_creator_lacks_permission"
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
MAX_LIST_PAGES = 50
DEFAULT_MIN_AGE_MINUTES = 60


# -- deleting what a run created -----------------------------------------------------
@dataclass
class DeleteResult:
    deleted: List[Tuple[str, str]] = field(default_factory=list)
    already_gone: List[Tuple[str, str]] = field(default_factory=list)
    # (id, label, why)
    left: List[Tuple[str, str, str]] = field(default_factory=list)
    missing_scope: bool = False
    creator_lacks_permission: bool = False


def delete_forms(key: Http, created: Sequence[Tuple[str, str]]) -> DeleteResult:
    """Delete each ``(form id, label)`` and nothing else. Never raises for an
    API error: a form that could not be deleted is listed in ``left``."""
    result = DeleteResult()
    seen = set()
    for form_id, label in created:
        if not form_id or form_id in seen:
            continue
        seen.add(form_id)
        if result.missing_scope:
            # every further call would be refused the same way
            result.left.append((form_id, label, "not tried: the key lacks the scope"))
            continue
        try:
            key.delete(f"/forms/{quote(form_id, safe='')}", expect=(204,))
            result.deleted.append((form_id, label))
        except HttpError as error:
            if error.status == 404:
                result.already_gone.append((form_id, label))
            elif error.status == 403 and error.code == MISSING_SCOPE_CODE:
                result.missing_scope = True
                result.left.append((form_id, label, f"missing scope {DELETE_SCOPE}"))
            elif error.status == 403 and error.code == CREATOR_LACKS_CODE:
                result.creator_lacks_permission = True
                result.left.append((form_id, label, "the key's creator lacks form.delete"))
            else:
                result.left.append((form_id, label, f"answered {error.status}"))
        except Exception as error:  # network trouble: the rest still gets its try
            result.left.append((form_id, label, type(error).__name__))
    return result


def describe(result: DeleteResult) -> Tuple[List[str], List[str]]:
    """``(notes, warnings)`` for the report: one note per form, and a warning
    when anything was left behind (never a failed check)."""
    notes = [f"{label} {fid} deleted" for fid, label in result.deleted]
    notes += [f"{label} {fid} was already gone" for fid, label in result.already_gone]
    notes += [f"{label} {fid} NOT deleted ({why})" for fid, label, why in result.left]
    warnings: List[str] = []
    if result.left:
        ids = ", ".join(fid for fid, _, _ in result.left)
        if result.missing_scope:
            cause = (
                f"the API key lacks the scope '{DELETE_SCOPE}'; add it to the "
                "key (docs/smoke-test.md), then remove these with the one-off "
                "cleanup (python -m smoke.cleanup)"
            )
        elif result.creator_lacks_permission:
            cause = (
                "the person who created the API key no longer has "
                "'form.delete' in the test workspace"
            )
        else:
            cause = "the delete was refused or failed (see the notes above)"
        warnings.append(
            f"{len(result.left)} form(s) left behind in the test workspace: "
            f"{ids}. {cause}."
        )
    return notes, warnings


# -- the one-off cleanup of old runs' forms ---------------------------------------------
def list_all_forms(key: Http) -> List[dict]:
    """Every form of the key's workspace, page by page."""
    items: List[dict] = []
    for page in range(1, MAX_LIST_PAGES + 1):
        body = key.get(f"/forms?page={page}&size=100").body or {}
        batch = body.get("items", []) if isinstance(body, dict) else []
        items.extend(batch)
        if len(batch) < 100:
            break
    return items


def _parse_time(value: object) -> Optional[dt.datetime]:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = dt.datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=dt.timezone.utc)


class Refused(Exception):
    """The cleanup stops before touching anything."""


@dataclass
class Plan:
    workspace_id: str = ""
    candidates: List[Tuple[str, str]] = field(default_factory=list)  # (id, title)
    too_recent: int = 0
    other_forms: int = 0


def verify_workspace(api: Http, listed: Sequence[dict], workspace: str) -> str:
    """The configured workspace's id, after checking that the forms the key
    lists belong to it (the suite's own safety check, repeated here)."""
    wanted = workspace
    body = None
    if OBJECT_ID.match(wanted):
        try:
            body = api.get(f"/workspaces/{wanted}").body
        except HttpError as error:
            if error.status not in (404, 422):
                raise
    if not isinstance(body, dict) or not body.get("id"):
        body = api.get(f"/workspaces?workspace_name={quote(wanted)}").body
    if not isinstance(body, dict) or not body.get("id"):
        raise Refused("SMOKE_WORKSPACE_ID names no workspace")
    workspace_id = str(body["id"])
    slug = next((str(f["slug"]) for f in listed if f.get("slug")), "")
    if not slug:
        raise Refused(
            "cannot tell which workspace the key belongs to (none of its forms "
            "is published): nothing was touched"
        )
    try:
        api.get(f"/workspaces/{workspace_id}/forms/{quote(slug, safe='')}?published=true")
    except HttpError as error:
        if error.status in (403, 404):
            raise Refused(
                "the API key's workspace is not SMOKE_WORKSPACE_ID: stopping"
            )
        raise
    return workspace_id


def plan_cleanup(
    api: Http,
    key: Http,
    workspace: str,
    now: dt.datetime,
    min_age_minutes: int = DEFAULT_MIN_AGE_MINUTES,
) -> Plan:
    listed = list_all_forms(key)
    plan = Plan(workspace_id=verify_workspace(api, listed, workspace))
    cutoff = now - dt.timedelta(minutes=min_age_minutes)
    for item in listed:
        form_id, title = str(item.get("formId") or ""), item.get("title")
        # first marker, from the list: the title's exact shape
        if not form_id or not (
            isinstance(title, str) and forms.RUN_TITLE.fullmatch(title)
        ):
            plan.other_forms += 1
            continue
        # second marker, from the stored form itself
        document = key.get(f"/forms/{quote(form_id, safe='')}").body
        trust = document.get("trust") if isinstance(document, dict) else None
        purpose = trust.get("purpose") if isinstance(trust, dict) else None
        if not (
            isinstance(document, dict)
            and document.get("title") == title
            and forms.is_run_form(title, purpose)
        ):
            plan.other_forms += 1
            continue
        updated = _parse_time(item.get("updatedAt"))
        if updated is not None and updated > cutoff:
            plan.too_recent += 1
            continue
        plan.candidates.append((form_id, title))
    return plan


def run_cleanup(
    api: Http,
    key: Http,
    workspace: str,
    *,
    delete: bool,
    min_age_minutes: int = DEFAULT_MIN_AGE_MINUTES,
    now: Optional[dt.datetime] = None,
    say: Callable[[str], None] = print,
) -> int:
    """0: done (or a dry run); 1: something could not be deleted; 2: refused."""
    now = now or dt.datetime.now(dt.timezone.utc)
    try:
        plan = plan_cleanup(api, key, workspace, now, min_age_minutes)
    except Refused as error:
        say(f"refused: {error}")
        return 2
    say(
        f"{len(plan.candidates)} smoke run form(s) match both markers; "
        f"{plan.too_recent} skipped (changed in the last {min_age_minutes} min); "
        f"{plan.other_forms} other form(s) not touched."
    )
    for form_id, title in plan.candidates:
        say(f"  {'delete' if delete else 'would delete'}: {form_id}  {title}")
    if not delete:
        if plan.candidates:
            say("Dry run: nothing was deleted. Add --delete to delete these.")
        return 0
    result = delete_forms(
        key, [(form_id, "old run form") for form_id, _ in plan.candidates]
    )
    notes, warnings = describe(result)
    for line in notes:
        say(f"  {line}")
    for line in warnings:
        say(f"WARNING: {line}")
    say(f"deleted {len(result.deleted)}, left {len(result.left)}.")
    return 1 if result.left else 0


# -- command line ----------------------------------------------------------------------
def _is_local(url: str) -> bool:
    return (urlsplit(url).hostname or "") in LOCAL_HOSTS


def _api_base(target: Optional[str], api_url: Optional[str]) -> str:
    if api_url:
        return normalize_url(api_url, "--api-url")
    if not target:
        raise ConfigError("SMOKE_APP_URL is not set (or pass --api-url)")
    candidate = normalize_url(target, "SMOKE_APP_URL") + "/api/v1"
    try:
        answers = isinstance(Http(candidate).get("/providers").body, list)
    except (HttpError, OSError, ValueError):
        answers = False
    if not answers:
        raise ConfigError(f"{candidate} does not answer: pass --api-url")
    return candidate


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m smoke.cleanup", description=__doc__.split("\n\n")[1]
    )
    parser.add_argument("--target", help="the web app's base URL (default: SMOKE_APP_URL)")
    parser.add_argument("--api-url", help="the API base (default: <target>/api/v1)")
    parser.add_argument(
        "--delete",
        action="store_true",
        help="really delete; without it this only lists what would be deleted",
    )
    parser.add_argument(
        "--min-age-minutes",
        type=int,
        default=DEFAULT_MIN_AGE_MINUTES,
        help="leave forms changed more recently than this (default: %(default)s)",
    )
    return parser.parse_args(list(argv))


def main(argv: Optional[Sequence[str]] = None, env: Mapping[str, str] = os.environ) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    redactor = Redactor()
    lines: List[str] = []

    def say(text: str) -> None:
        clean = redactor.scrub(text)
        lines.append(clean)
        print(clean)

    try:
        api_key = (env.get("SMOKE_API_KEY") or "").strip()
        if not api_key:
            raise ConfigError("SMOKE_API_KEY is not set")
        if not re.fullmatch(r"bc_[A-Za-z0-9]{16,128}", api_key):
            raise ConfigError("SMOKE_API_KEY does not look like a workspace API key")
        redactor.add(api_key)
        workspace = (env.get("SMOKE_WORKSPACE_ID") or "").strip()
        if not workspace:
            raise ConfigError("SMOKE_WORKSPACE_ID is not set")
        if not (OBJECT_ID.match(workspace) or HANDLE.match(workspace)):
            raise ConfigError("SMOKE_WORKSPACE_ID must be a workspace id or name")
        if args.min_age_minutes < 0:
            raise ConfigError("--min-age-minutes must not be negative")
        api_base = _api_base(args.target or env.get("SMOKE_APP_URL"), args.api_url)
        if urlsplit(api_base).scheme != "https" and not _is_local(api_base):
            raise ConfigError("refusing to send the API key over plain http")
    except ConfigError as error:
        print(redactor.scrub(f"configuration: {error}"), file=sys.stderr)
        return 2

    api = Http(api_base)
    key = Http(api_base + "/public/v1", headers={"Authorization": f"Bearer {api_key}"})
    say(f"Smoke cleanup ({'DELETE' if args.delete else 'dry run'}) on {api_base}")
    try:
        code = run_cleanup(
            api,
            key,
            workspace,
            delete=args.delete,
            min_age_minutes=args.min_age_minutes,
            say=say,
        )
    except (HttpError, OSError) as error:
        say(f"stopped: {error}")
        code = 1
    summary = env.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as handle:
            handle.write("### Smoke cleanup\n\n```\n" + "\n".join(lines) + "\n```\n")
    return code


if __name__ == "__main__":
    sys.exit(main())
