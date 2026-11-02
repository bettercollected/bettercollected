"""``bettercollected``: forms as code.

    bettercollected pull <form-id> -o form.json      (or form.yaml)
    bettercollected diff form.json                   what push would change
    bettercollected push form.json [--force]         replace the form
    bettercollected validate form.json
    bettercollected create form.json                 a new draft from a file
    bettercollected promote <form-id> --to production [--from staging]
                            [--to-form <form-id>] [--dry-run] [--copy-privacy]
    bettercollected submit <form-id> answers.json --consent [--consent-item ID ...]
    bettercollected update-submission <form-id> <response-id> answers.json

JSON is the canonical format; YAML (.yaml/.yml) is read and written too.
The API key comes from ``BETTERCOLLECTED_API_KEY`` only (never a flag, so it
stays out of shell history); the instance from ``--url`` or
``BETTERCOLLECTED_URL``.

``promote`` copies a form's document from one workspace (environment) to
another, as a draft: a new form, or the draft of ``--to-form``. Keys never
come from the command line: ``BETTERCOLLECTED_<NAME>_API_KEY`` and
``BETTERCOLLECTED_<NAME>_URL`` for an environment called ``<NAME>``, or a
private config file (see docs/environments.md).

``pull`` remembers each file's form id and version (ETag) in
``.bettercollected.json`` next to the file. ``push`` replaces the form only
while it is still that version; ``--force`` fetches the current version
first and overwrites whatever changed on the server.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import re
import stat
import sys
import uuid
from pathlib import Path
from typing import Any, Sequence

import httpx
import yaml

from bettercollected import promote as promotion
from bettercollected.client import BetterCollected, BetterCollectedError

API_KEY_ENV = "BETTERCOLLECTED_API_KEY"
URL_ENV = "BETTERCOLLECTED_URL"
CONFIG_ENV = "BETTERCOLLECTED_CONFIG"
STATE_FILE = ".bettercollected.json"
_ENV_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,31}$")


class CliError(Exception):
    pass


# -- files ---------------------------------------------------------------------


def _is_yaml(path: Path) -> bool:
    return path.suffix.lower() in (".yaml", ".yml")


def read_document(path: Path) -> Any:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise CliError(f"Cannot read {path}: {error.strerror}") from error
    try:
        return yaml.safe_load(text) if _is_yaml(path) else json.loads(text)
    except (ValueError, yaml.YAMLError) as error:
        raise CliError(
            f"{path} is not valid {'YAML' if _is_yaml(path) else 'JSON'}: {error}"
        ) from error


def write_document(path: Path, document: Any) -> None:
    if _is_yaml(path):
        text = yaml.safe_dump(document, sort_keys=False, allow_unicode=True)
    else:
        text = json.dumps(document, indent=2, ensure_ascii=False) + "\n"
    path.write_text(text, encoding="utf-8")


def _state_path(path: Path) -> Path:
    return path.resolve().parent / STATE_FILE


def load_state(path: Path) -> dict:
    state_path = _state_path(path)
    if not state_path.exists():
        return {}
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except ValueError:
        return {}
    return (state.get("forms") or {}).get(path.name) or {}


def save_state(path: Path, form_id: str, etag: str) -> None:
    state_path = _state_path(path)
    state = {"forms": {}}
    if state_path.exists():
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except ValueError:
            pass
    state.setdefault("forms", {})[path.name] = {"formId": form_id, "etag": etag}
    state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


# -- commands ------------------------------------------------------------------


def _client(args) -> BetterCollected:
    api_key = os.environ.get(API_KEY_ENV, "")
    if not api_key:
        raise CliError(f"Set {API_KEY_ENV} to a workspace API key.")
    url = args.url or os.environ.get(URL_ENV, "")
    if not url:
        raise CliError(f"Pass --url or set {URL_ENV} to the instance's address.")
    return BetterCollected(api_key, url)


def _form_id(args, path: Path) -> str:
    form_id = args.form_id or load_state(path).get("formId")
    if not form_id:
        raise CliError(f"No form id for {path.name}: pull it first or pass --form-id.")
    return form_id


def cmd_pull(args, out) -> int:
    path = Path(args.output)
    with _client(args) as client:
        current = client.get_form_document(args.form_id)
    write_document(path, current.value)
    save_state(path, args.form_id, current.etag)
    print(f"Pulled {args.form_id} to {path}", file=out)
    return 0


def _print_diff(diff: dict, out) -> None:
    for change in diff.get("form") or []:
        print(
            f"~ {change['path']}: {json.dumps(change.get('before'))} -> "
            f"{json.dumps(change.get('after'))}",
            file=out,
        )
    for part in ("pages", "fields"):
        section = diff.get(part) or {}
        for item in section.get("added") or []:
            print(f"+ {part[:-1]} {item.get('id')} at {item.get('path')}", file=out)
        for item in section.get("removed") or []:
            print(f"- {part[:-1]} {item.get('id')} (was {item.get('path')})", file=out)
        for item in section.get("moved") or []:
            print(
                f"> {part[:-1]} {item.get('id')} moved {item.get('from')} -> "
                f"{item.get('to')}",
                file=out,
            )
        for item in section.get("changed") or []:
            for change in item.get("changes") or []:
                print(
                    f"~ {change['path']}: {json.dumps(change.get('before'))} -> "
                    f"{json.dumps(change.get('after'))}",
                    file=out,
                )


def cmd_diff(args, out) -> int:
    path = Path(args.file)
    document = read_document(path)
    form_id = _form_id(args, path)
    with _client(args) as client:
        current = client.get_form_document(form_id)
        preview = client.preview_replace(form_id, document)
    stored = load_state(path).get("etag")
    if stored and stored != current.etag:
        print(
            "! The form changed on the server since it was pulled; push needs "
            "--force (or pull again).",
            file=out,
        )
    if not preview.valid:
        print(f"{path} is not valid:", file=out)
        for error in preview.errors:
            print(f"  {error.path or '/'}: {error.message}", file=out)
        return 1
    if not (preview.diff or {}).get("changed"):
        print("No changes.", file=out)
        return 0
    _print_diff(preview.diff or {}, out)
    return 0


def cmd_push(args, out) -> int:
    path = Path(args.file)
    document = read_document(path)
    form_id = _form_id(args, path)
    with _client(args) as client:
        if args.force:
            etag = client.get_form_document(form_id).etag
        else:
            etag = load_state(path).get("etag")
            if not etag:
                raise CliError(
                    f"No version recorded for {path.name}: pull it first, or "
                    "push --force to overwrite the current version."
                )
        try:
            replaced = client.replace_form(form_id, document, if_match=etag)
        except BetterCollectedError as error:
            if error.status == 412:
                raise CliError(
                    "The form changed on the server since it was pulled. Run "
                    "diff, pull again, or push --force to overwrite it."
                ) from error
            raise
    save_state(path, form_id, replaced.etag)
    print(f"Pushed {path} to {form_id}", file=out)
    return 0


# -- environments --------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class Environment:
    """One workspace: where it is and the key that opens it. The key stays out
    of the repr, so it cannot reach an error message or a log."""

    name: str
    url: str
    api_key: str = dataclasses.field(repr=False)


def _config_path(explicit: str | None) -> tuple[Path, bool]:
    """The config file and whether the person named it (then it must exist)."""
    if explicit:
        return Path(explicit), True
    from_env = os.environ.get(CONFIG_ENV)
    if from_env:
        return Path(from_env), True
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "bettercollected" / "config.yaml", False


def _config_entry(name: str, explicit: str | None) -> tuple[dict, Path | None]:
    path, named = _config_path(explicit)
    if not path.exists():
        if named:
            raise CliError(f"Config file {path} does not exist.")
        return {}, None
    document = read_document(path)
    environments = document.get("environments") if isinstance(document, dict) else None
    entry = environments.get(name) if isinstance(environments, dict) else None
    if entry is None:
        return {}, path
    if not isinstance(entry, dict):
        raise CliError(f"{path}: environment {name} must be an object.")
    return entry, path


def _refuse_open_config(path: Path) -> None:
    """A file with a key in it must not be readable by other users."""
    if os.name != "posix":
        return
    if stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise CliError(
            f"{path} holds an API key but other users can read it. "
            f"Run: chmod 600 {path}"
        )


def resolve_environment(
    name: str | None, args, *, default_url: str | None = None
) -> Environment:
    """The environment ``name``, from the process environment and then the
    config file. ``None`` is the unnamed one (``BETTERCOLLECTED_API_KEY`` and
    ``--url``/``BETTERCOLLECTED_URL``). A key is never read from a flag."""
    if name is None:
        key = os.environ.get(API_KEY_ENV, "")
        url = getattr(args, "url", None) or os.environ.get(URL_ENV, "")
        if not key:
            raise CliError(f"Set {API_KEY_ENV} to a workspace API key.")
        if not url:
            raise CliError(f"Pass --url or set {URL_ENV} to the instance's address.")
        return Environment("default", url, key)
    if not _ENV_NAME.match(name):
        raise CliError(
            f"{name!r} is not an environment name (letters, digits, _ and -)."
        )
    prefix = "BETTERCOLLECTED_" + re.sub(r"[^A-Za-z0-9]", "_", name).upper()
    key_var, url_var = f"{prefix}_API_KEY", f"{prefix}_URL"
    key = os.environ.get(key_var, "")
    url = os.environ.get(url_var, "")
    if not key or not url:
        entry, path = _config_entry(name, getattr(args, "config", None))
        url = url or str(entry.get("url") or "")
        if not key:
            holder = entry.get("api_key_env")
            if holder:
                key = os.environ.get(str(holder), "")
                if not key:
                    raise CliError(
                        f"Environment {name}: set {holder} (named by api_key_env)."
                    )
            elif entry.get("api_key") and path is not None:
                _refuse_open_config(path)
                key = str(entry["api_key"])
    if not key:
        raise CliError(
            f"No API key for environment {name}: set {key_var}, or api_key_env "
            "in the config file."
        )
    url = url or default_url or ""
    if not url:
        raise CliError(f"No address for environment {name}: set {url_var}.")
    return Environment(name, url, key)


def _list_map(path: str | None) -> dict[str, str]:
    if not path:
        return {}
    document = read_document(Path(path))
    if not isinstance(document, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in document.items()
    ):
        raise CliError(
            f"{path} must hold an object of option list ids: "
            '{"<source list id>": "<target list id>"}.'
        )
    return document


def _create_form(client, document, idempotency_key):
    """``client.create_form``, with a hint for a key that may not create forms
    (limited to certain forms by an admin)."""
    try:
        return client.create_form(document, idempotency_key=idempotency_key)
    except BetterCollectedError as error:
        if error.code == "key_form_scope":
            raise CliError(
                "This API key is limited to certain forms, so it cannot create "
                "a form. Create the form in the product, or ask a workspace "
                "admin for a key that is not limited to forms."
            ) from error
        raise


def cmd_create(args, out) -> int:
    path = Path(args.file)
    known = load_state(path).get("formId")
    if known:
        raise CliError(f"{path.name} already belongs to form {known}: use push.")
    document = read_document(path)
    with _client(args) as client:
        created = _create_form(client, document, args.idempotency_key)
    save_state(path, created.form_id, created.etag)
    print(f"Created draft {created.form_id} from {path}", file=out)
    print("It is not published: publish it when it is ready.", file=out)
    return 0


def cmd_promote(args, out) -> int:
    source = resolve_environment(args.source, args)
    target = resolve_environment(args.target, args, default_url=source.url)
    shared_storage = promotion.same_instance(source.url, target.url)
    if (
        shared_storage
        and source.api_key == target.api_key
        and args.to_form == args.form_id
    ):
        raise CliError("The source and the target are the same form.")
    list_map = _list_map(args.list_map)
    updating = bool(args.to_form)

    with BetterCollected(source.api_key, source.url) as source_client:
        pulled = source_client.get_form_document(args.form_id)
    document, report = promotion.normalise(
        pulled.value,
        shared_storage=shared_storage,
        list_map=list_map,
        keep_target_privacy=updating and not args.copy_privacy,
    )

    with BetterCollected(target.api_key, target.url) as client:
        current = client.get_form_document(args.to_form) if updating else None
        if updating:
            preview = client.preview_replace(args.to_form, document)
            problems, warnings = preview.errors, preview.warnings
        else:
            preview = None
            checked = client.validate_form(document)
            problems, warnings = checked.errors, checked.warnings

        print(f"{source.name} -> {target.name}", file=out)
        promotion.render_report(report, out)
        for warning in warnings:
            print(f"warning {warning.path or '/'}: {warning.message}", file=out)
        if problems:
            print(
                f"The target would refuse this form ({len(problems)} problem(s)); "
                "nothing was written:",
                file=out,
            )
            for problem in problems:
                print(f"  {problem.path or '/'}: {problem.message}", file=out)
            return 1

        if updating:
            if args.copy_privacy and promotion.retention_shortened(
                (current.value.get("trust") or {}).get("retention"),
                (document.get("trust") or {}).get("retention"),
            ):
                print(
                    "warning: --copy-privacy changes how long the target keeps "
                    "answers, possibly to less than now.",
                    file=out,
                )
            if not (preview.diff or {}).get("changed"):
                print("No changes: the target draft is already the same.", file=out)
                return 0
            print(f"Changes to the draft of {args.to_form}:", file=out)
            _print_diff(preview.diff or {}, out)
        else:
            pages, questions = promotion.count_questions(document)
            print(
                f"A new draft with {pages} page(s) and {questions} question(s).",
                file=out,
            )

        if args.dry_run:
            print("Dry run: nothing was written.", file=out)
            return 0

        if updating:
            try:
                client.replace_form(args.to_form, document, if_match=current.etag)
            except BetterCollectedError as error:
                if error.status == 412:
                    raise CliError(
                        "The target form changed while you were reviewing. "
                        "Run the command again."
                    ) from error
                raise
            print(f"Updated the draft of {args.to_form}.", file=out)
        else:
            created = _create_form(client, document, uuid.uuid4().hex)
            print(f"Created draft {created.form_id}.", file=out)
    print("It is a draft: review it and publish it in the target when ready.", file=out)
    return 0


def cmd_validate(args, out) -> int:
    path = Path(args.file)
    document = read_document(path)
    with _client(args) as client:
        result = client.validate_form(document)
    for error in result.errors:
        print(f"error   {error.path or '/'}: {error.message}", file=out)
    for warning in result.warnings:
        print(f"warning {warning.path or '/'}: {warning.message}", file=out)
    print(f"{path}: {'valid' if result.valid else 'not valid'}", file=out)
    return 0 if result.valid else 1


def _answers_body(path: Path) -> dict:
    """The file of a submission: ``{"answers": {...}}`` (``hiddenFields`` is
    optional). Nothing else is sent: consent is the command line's to assert."""
    document = read_document(path)
    if not isinstance(document, dict) or not isinstance(document.get("answers"), dict):
        raise CliError(f'{path} must hold an object with an "answers" object.')
    unknown = set(document) - {"answers", "hiddenFields"}
    if unknown:
        raise CliError(
            f"{path} has keys the submission does not take: {', '.join(sorted(unknown))}."
        )
    return document


def cmd_submit(args, out) -> int:
    body = _answers_body(Path(args.file))
    with _client(args) as client:
        created = client.create_submission(
            args.form_id,
            body["answers"],
            consent=True if args.consent else None,
            consent_items=args.consent_item or None,
            hidden_fields=body.get("hiddenFields"),
            idempotency_key=args.idempotency_key,
        )
    print(f"Submitted: response {created.response_id}", file=out)
    return 0


def cmd_update_submission(args, out) -> int:
    body = _answers_body(Path(args.file))
    with _client(args) as client:
        updated = client.update_submission(
            args.form_id, args.response_id, body["answers"]
        )
    print(f"Updated: response {updated.response_id}", file=out)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bettercollected",
        description="Forms as code for BetterCollected. The API key is read from "
        f"{API_KEY_ENV}.",
    )
    parser.add_argument("--url", help=f"The instance's address (or {URL_ENV}).")
    commands = parser.add_subparsers(dest="command", required=True)

    pull = commands.add_parser("pull", help="Write a form to a file.")
    pull.add_argument("form_id")
    pull.add_argument("-o", "--output", required=True, help="form.json or form.yaml")
    pull.set_defaults(run=cmd_pull)

    for name, run, text in (
        ("diff", cmd_diff, "Show what push would change."),
        ("push", cmd_push, "Replace the form with the file."),
    ):
        command = commands.add_parser(name, help=text)
        command.add_argument("file")
        command.add_argument(
            "--form-id", help="Defaults to the form the file was pulled from."
        )
        if name == "push":
            command.add_argument(
                "--force",
                action="store_true",
                help="Overwrite the current version, even if it changed since the pull.",
            )
        command.set_defaults(run=run)

    submit = commands.add_parser(
        "submit",
        help="Submit a response to a published form (needs the submissions:write scope).",
    )
    submit.add_argument("form_id")
    submit.add_argument("file", help='JSON or YAML: {"answers": {"<question id>": ...}}')
    submit.add_argument(
        "--consent",
        action="store_true",
        help="Assert that the respondent has given the consent the form requires.",
    )
    submit.add_argument(
        "--consent-item",
        action="append",
        metavar="ID",
        help="An optional consent item the respondent accepted (repeat for several).",
    )
    submit.add_argument("--idempotency-key", help="Makes a retry safe (24 hours).")
    submit.set_defaults(run=cmd_submit)

    update = commands.add_parser(
        "update-submission",
        help="Change answers of a response this API key made.",
    )
    update.add_argument("form_id")
    update.add_argument("response_id")
    update.add_argument("file", help='JSON or YAML: {"answers": {"<question id>": ...}}')
    update.set_defaults(run=cmd_update_submission)

    create = commands.add_parser(
        "create", help="Create a new draft form from a file (never publishes)."
    )
    create.add_argument("file")
    create.add_argument("--idempotency-key", help="Makes a retry safe (24 hours).")
    create.set_defaults(run=cmd_create)

    promote = commands.add_parser(
        "promote",
        help="Copy a form to another workspace or instance, as a draft.",
        description="Copy a form's document (never its answers, automations, "
        "sharing, link or publish state) from one environment to another. "
        "Keys come from BETTERCOLLECTED_<NAME>_API_KEY (or a private config "
        "file), never from a flag.",
    )
    promote.add_argument("form_id", help="The form in the source environment.")
    promote.add_argument(
        "--from",
        dest="source",
        metavar="NAME",
        help="Source environment (default: BETTERCOLLECTED_API_KEY and --url).",
    )
    promote.add_argument(
        "--to", dest="target", metavar="NAME", required=True, help="Target environment."
    )
    promote.add_argument(
        "--to-form",
        metavar="FORM_ID",
        help="Update the draft of this form in the target (default: a new form).",
    )
    promote.add_argument(
        "--dry-run", action="store_true", help="Show the changes; write nothing."
    )
    promote.add_argument(
        "--copy-privacy",
        action="store_true",
        help="Also copy retention, purpose and privacy link into an existing "
        "target form (otherwise it keeps its own).",
    )
    promote.add_argument(
        "--list-map",
        metavar="FILE",
        help='JSON or YAML {"<source list id>": "<target list id>"} for option lists.',
    )
    promote.add_argument(
        "--config",
        metavar="FILE",
        help=f"Config file with named environments (or {CONFIG_ENV}).",
    )
    promote.set_defaults(run=cmd_promote)

    validate = commands.add_parser("validate", help="Check a file.")
    validate.add_argument("file")
    validate.set_defaults(run=cmd_validate)
    return parser


def main(argv: Sequence[str] | None = None, out=None, err=None) -> int:
    out = out or sys.stdout
    err = err or sys.stderr
    args = build_parser().parse_args(argv)
    try:
        return args.run(args, out)
    except CliError as error:
        print(f"error: {error}", file=err)
        return 1
    except BetterCollectedError as error:
        print(f"error: {error}", file=err)
        return 1
    except httpx.HTTPError as error:
        # httpx's messages name the problem, never the request headers
        print(f"error: the request failed ({type(error).__name__}: {error})", file=err)
        return 1


if __name__ == "__main__":
    sys.exit(main())
