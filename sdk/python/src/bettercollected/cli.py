"""``bettercollected``: forms as code.

    bettercollected pull <form-id> -o form.json      (or form.yaml)
    bettercollected diff form.json                   what push would change
    bettercollected push form.json [--force]         replace the form
    bettercollected validate form.json

JSON is the canonical format; YAML (.yaml/.yml) is read and written too.
The API key comes from ``BETTERCOLLECTED_API_KEY`` only (never a flag, so it
stays out of shell history); the instance from ``--url`` or
``BETTERCOLLECTED_URL``.

``pull`` remembers each file's form id and version (ETag) in
``.bettercollected.json`` next to the file. ``push`` replaces the form only
while it is still that version; ``--force`` fetches the current version
first and overwrites whatever changed on the server.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Sequence

import yaml

from bettercollected.client import BetterCollected, BetterCollectedError

API_KEY_ENV = "BETTERCOLLECTED_API_KEY"
URL_ENV = "BETTERCOLLECTED_URL"
STATE_FILE = ".bettercollected.json"


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


if __name__ == "__main__":
    sys.exit(main())
