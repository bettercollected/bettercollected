#!/usr/bin/env python3
"""Changelog fragments: preview them, assemble them into CHANGELOG.md, check a pull request.

A pull request adds its changelog entry as a file in changelog.d/ instead of editing
CHANGELOG.md, so pull requests no longer conflict on it. See changelog.d/README.md.

Usage (Python standard library only; run with `python3 -I` or `uv run --no-project python -I`):

  changelog.py assemble --draft
      Print the [Unreleased] section as it would be with every fragment added. Changes nothing.
  changelog.py assemble X.Y.Z [--date YYYY-MM-DD] [--previous A.B.C]
      Move the [Unreleased] entries and every fragment into a new `## [X.Y.Z] - date` section,
      leave an empty [Unreleased], add the compare link and delete the fragments.
  changelog.py check
      Pull request check (CI). Reads CHANGED_FILES (newline separated; default: the diff of
      the PR merge commit against its base, HEAD^1..HEAD), HEAD_REF, PR_LABELS (JSON list or
      comma separated) and PR_AUTHOR from the environment.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

# Keep a Changelog categories, in the order CHANGELOG.md lists them.
CATEGORIES = ("added", "changed", "deprecated", "removed", "fixed", "security")
FRAGMENT_DIR = "changelog.d"
IGNORED_FILES = {"README.md", ".gitkeep"}
FRAGMENT_NAME = re.compile(r"^(?P<name>[A-Za-z0-9][A-Za-z0-9._-]*)\.(?P<category>[a-z]+)\.md$")
VERSION = re.compile(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$")
UNRELEASED = re.compile(r"^## \[Unreleased\]\s*$")
RELEASE_HEADING = re.compile(r"^## \[(?P<version>[^\]]+)\]")
LINK_REF = re.compile(r"^\[(?P<label>[^\]]+)\]: (?P<url>\S+)\s*$")
REPO_URL = re.compile(r"^(?P<base>https://github\.com/[^/]+/[^/]+)/(?:compare|releases)/")

NO_CHANGELOG_LABEL = "no-changelog"
ASSEMBLY_BRANCH_PREFIX = "docs/changelog-"
# Pull requests that only move already-reviewed changes between long-lived branches.
SYNC_BRANCH = re.compile(r"^(develop|master|main|release/.+)$")
BOT_AUTHORS = {"dependabot[bot]"}


class ChangelogError(Exception):
    pass


@dataclass(frozen=True)
class Fragment:
    path: Path
    name: str
    category: str
    text: str

    @property
    def sort_key(self) -> tuple:
        # PR numbers in numeric order first, then branch slugs alphabetically.
        if self.name.isdigit():
            return (0, int(self.name), self.name, self.category)
        return (1, 0, self.name.lower(), self.name, self.category)


def default_root() -> Path:
    return Path(__file__).resolve().parents[2]


# --- fragments ---------------------------------------------------------------------------


def validate_text(text: str, label: str) -> str:
    text = text.replace("\r\n", "\n").strip("\n").rstrip()
    if not text.strip():
        raise ChangelogError(f"{label}: the fragment is empty")
    lines = text.split("\n")
    if not lines[0].startswith("- "):
        raise ChangelogError(f"{label}: the first line must start a bullet ('- ')")
    for number, line in enumerate(lines, 1):
        if not line.strip():
            raise ChangelogError(f"{label}:{number}: blank line inside the fragment")
        if line.startswith("#"):
            raise ChangelogError(f"{label}:{number}: no headings; the file name gives the category")
        if not (line.startswith("- ") or line.startswith(" ")):
            raise ChangelogError(
                f"{label}:{number}: each line starts a bullet ('- ') or continues one (indented)"
            )
    return "\n".join(line.rstrip() for line in lines)


def parse_fragment_name(filename: str) -> tuple[str, str]:
    match = FRAGMENT_NAME.match(filename)
    if not match:
        raise ChangelogError(
            f"{FRAGMENT_DIR}/{filename}: name it <pr-number-or-branch-slug>.<category>.md"
        )
    category = match["category"]
    if category not in CATEGORIES:
        raise ChangelogError(
            f"{FRAGMENT_DIR}/{filename}: unknown category '{category}' "
            f"(one of: {', '.join(CATEGORIES)})"
        )
    return match["name"], category


def load_fragments(root: Path) -> list[Fragment]:
    directory = root / FRAGMENT_DIR
    if not directory.is_dir():
        return []
    fragments = []
    errors = []
    for path in sorted(directory.iterdir()):
        if path.name in IGNORED_FILES:
            continue
        try:
            if not path.is_file():
                raise ChangelogError(f"{FRAGMENT_DIR}/{path.name}: only files belong here")
            name, category = parse_fragment_name(path.name)
            text = validate_text(path.read_text(encoding="utf-8"), f"{FRAGMENT_DIR}/{path.name}")
            fragments.append(Fragment(path, name, category, text))
        except ChangelogError as error:
            errors.append(str(error))
    if errors:
        raise ChangelogError("\n".join(errors))
    return sorted(fragments, key=lambda fragment: fragment.sort_key)


# --- CHANGELOG.md ------------------------------------------------------------------------


@dataclass
class Document:
    head: list[str]  # up to and including the [Unreleased] heading
    preamble: list[str]  # text in [Unreleased] before its first category
    sections: dict[str, list[str]]  # category -> its lines, without surrounding blanks
    tail: list[str]  # from the first heading after [Unreleased] to the end


def trim(lines: list[str]) -> list[str]:
    start, end = 0, len(lines)
    while start < end and not lines[start].strip():
        start += 1
    while end > start and not lines[end - 1].strip():
        end -= 1
    return lines[start:end]


def parse_changelog(text: str) -> Document:
    lines = text.split("\n")
    start = next((i for i, line in enumerate(lines) if UNRELEASED.match(line)), None)
    if start is None:
        raise ChangelogError("CHANGELOG.md has no '## [Unreleased]' heading")
    end = next(
        (
            i
            for i in range(start + 1, len(lines))
            if lines[i].startswith("## ") or LINK_REF.match(lines[i])
        ),
        len(lines),
    )
    preamble: list[str] = []
    sections: dict[str, list[str]] = {}
    current: list[str] = preamble
    for line in lines[start + 1 : end]:
        if line.startswith("### "):
            category = line[4:].strip().lower()
            if category not in CATEGORIES:
                raise ChangelogError(f"CHANGELOG.md [Unreleased]: unknown category '{line[4:].strip()}'")
            if category in sections:
                raise ChangelogError(f"CHANGELOG.md [Unreleased]: '{line}' appears twice")
            current = sections[category] = []
        elif line.startswith("#"):
            raise ChangelogError(f"CHANGELOG.md [Unreleased]: unexpected heading '{line}'")
        else:
            current.append(line)
    return Document(
        head=lines[: start + 1],
        preamble=trim(preamble),
        sections={category: trim(body) for category, body in sections.items()},
        tail=lines[end:],
    )


def merged_sections(document: Document, fragments: list[Fragment]) -> dict[str, list[str]]:
    sections = {category: list(body) for category, body in document.sections.items()}
    for fragment in fragments:
        sections.setdefault(fragment.category, []).extend(fragment.text.split("\n"))
    return {category: sections[category] for category in CATEGORIES if sections.get(category)}


def render_body(preamble: list[str], sections: dict[str, list[str]]) -> list[str]:
    out: list[str] = []
    if preamble:
        out += preamble + [""]
    for category, body in sections.items():
        out += [f"### {category.capitalize()}", ""] + body + [""]
    return out


def draft(root: Path) -> str:
    document = parse_changelog((root / "CHANGELOG.md").read_text(encoding="utf-8"))
    fragments = load_fragments(root)
    body = render_body(document.preamble, merged_sections(document, fragments))
    return "\n".join(["## [Unreleased]", ""] + body)


def add_links(tail: list[str], version: str, previous: str | None) -> list[str]:
    refs = [(i, LINK_REF.match(line)) for i, line in enumerate(tail)]
    refs = [(i, match) for i, match in refs if match]
    base = next((REPO_URL.match(m["url"])["base"] for _, m in refs if REPO_URL.match(m["url"])), None)
    if base is None:
        return tail
    tail = list(tail)
    unreleased = next((i for i, m in refs if m["label"].lower() == "unreleased"), None)
    if unreleased is not None:
        tail[unreleased] = f"[Unreleased]: {base}/compare/v{version}...HEAD"
    if any(m["label"] == version for _, m in refs):
        return tail
    if previous:
        link = f"[{version}]: {base}/compare/v{previous}...v{version}"
    else:
        link = f"[{version}]: {base}/releases/tag/v{version}"
    first_version = next((i for i, m in refs if m["label"].lower() != "unreleased"), None)
    position = first_version if first_version is not None else len(trim(tail))
    tail.insert(position, link)
    return tail


def assemble(root: Path, version: str, date: str, previous: str | None = None) -> list[Path]:
    if not VERSION.match(version):
        raise ChangelogError(f"'{version}' is not a version (X.Y.Z)")
    datetime.date.fromisoformat(date)
    changelog = root / "CHANGELOG.md"
    document = parse_changelog(changelog.read_text(encoding="utf-8"))
    released = [m["version"] for line in document.tail if (m := RELEASE_HEADING.match(line))]
    if version in released:
        raise ChangelogError(f"CHANGELOG.md already has a [{version}] section")
    fragments = load_fragments(root)
    sections = merged_sections(document, fragments)
    if not sections:
        raise ChangelogError("nothing to release: [Unreleased] is empty and there are no fragments")
    if previous is None and released:
        previous = released[0]
    lines = (
        document.head
        + ["", f"## [{version}] - {date}", ""]
        + render_body(document.preamble, sections)
        + add_links(document.tail, version, previous)
    )
    changelog.write_text("\n".join(lines), encoding="utf-8")
    for fragment in fragments:
        fragment.path.unlink()
    return [fragment.path for fragment in fragments]


# --- pull request check ------------------------------------------------------------------

TEST_DIRS = {"tests", "test", "__tests__", "__mocks__"}
TEST_FILE = re.compile(r"^(conftest\.py|test_.*\.py|.*_test\.py|.*\.(test|spec)\.[cm]?[jt]sx?)$")
NON_CODE_PREFIXES = ("docs/", f"{FRAGMENT_DIR}/", ".github/ISSUE_TEMPLATE/")
NON_CODE_FILES = {".github/CODEOWNERS", ".github/FUNDING.yml", "AUTHORS"}


def needs_entry(path: str) -> bool:
    """Whether a changed path is a change the changelog should mention (code, config, CI).

    Exempt: prose (docs/**, every *.md), the fragments themselves, repository metadata
    (.github/ISSUE_TEMPLATE/**, CODEOWNERS, FUNDING.yml, AUTHORS) and tests (a tests/,
    test/, __tests__/ or __mocks__/ directory; test_*.py, *_test.py, conftest.py,
    *.test.* and *.spec.* scripts).
    """
    p = PurePosixPath(path)
    if path.endswith(".md") or path.startswith(NON_CODE_PREFIXES) or path in NON_CODE_FILES:
        return False
    if TEST_DIRS.intersection(p.parts[:-1]) or TEST_FILE.match(p.name):
        return False
    return True


def parse_labels(raw: str) -> set[str]:
    raw = raw.strip()
    if not raw:
        return set()
    if raw.startswith("["):
        return {str(label) for label in json.loads(raw)}
    return {label.strip() for label in raw.split(",") if label.strip()}


def check(root: Path, changed: list[str], head_ref: str, labels: set[str], author: str) -> list[str]:
    """Return the problems (empty: the pull request passes)."""
    if SYNC_BRANCH.match(head_ref):
        print(f"'{head_ref}' is a branch sync; no changelog check.")
        return []
    problems = []
    try:
        load_fragments(root)
    except ChangelogError as error:
        problems += str(error).split("\n")
    assembly = head_ref.startswith(ASSEMBLY_BRANCH_PREFIX)
    if "CHANGELOG.md" in changed and not assembly:
        problems.append(
            "CHANGELOG.md is edited directly: add the entry as a file in changelog.d/ instead "
            f"(see changelog.d/README.md). Only release branches ({ASSEMBLY_BRANCH_PREFIX}X.Y.Z) "
            "edit CHANGELOG.md."
        )
    if assembly:
        return problems
    fragments = [
        path
        for path in changed
        if path.startswith(f"{FRAGMENT_DIR}/")
        and PurePosixPath(path).name not in IGNORED_FILES
        and (root / path).is_file()
    ]
    code = [path for path in changed if needs_entry(path)]
    if fragments or not code:
        print(f"{len(fragments)} fragment(s), {len(code)} file(s) that need an entry.")
        return problems
    if NO_CHANGELOG_LABEL in labels:
        print(f"Label '{NO_CHANGELOG_LABEL}': no fragment needed.")
        return problems
    if author in BOT_AUTHORS:
        print(f"{author}: dependency updates are noted when they are folded into a release.")
        return problems
    shown = ", ".join(code[:10]) + (f" and {len(code) - 10} more" if len(code) > 10 else "")
    problems.append(
        "No changelog fragment: add changelog.d/<pr-number-or-branch-slug>.<category>.md "
        f"(see changelog.d/README.md), or label the pull request '{NO_CHANGELOG_LABEL}' "
        f"when nothing user- or operator-facing changed. Files that need an entry: {shown}"
    )
    return problems


def changed_files_from_env(root: Path) -> list[str]:
    raw = os.environ.get("CHANGED_FILES")
    if raw is None:
        raw = subprocess.run(
            ["git", "diff", "--name-only", "HEAD^1", "HEAD"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    return [line.strip() for line in raw.splitlines() if line.strip()]


# --- command line ------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--root", type=Path, default=default_root(), help="repository root")
    commands = parser.add_subparsers(dest="command", required=True)
    assemble_parser = commands.add_parser("assemble", help="release the fragments")
    assemble_parser.add_argument("version", nargs="?", help="X.Y.Z (not with --draft)")
    assemble_parser.add_argument("--draft", action="store_true", help="print, change nothing")
    assemble_parser.add_argument("--date", default=datetime.date.today().isoformat())
    assemble_parser.add_argument("--previous", help="version the compare link starts from")
    commands.add_parser("check", help="pull request check (reads the environment)")
    args = parser.parse_args(argv)

    try:
        if args.command == "check":
            problems = check(
                args.root,
                changed_files_from_env(args.root),
                os.environ.get("HEAD_REF", ""),
                parse_labels(os.environ.get("PR_LABELS", "")),
                os.environ.get("PR_AUTHOR", ""),
            )
            prefix = "::error::" if os.environ.get("GITHUB_ACTIONS") == "true" else "error: "
            for problem in problems:
                print(prefix + problem, file=sys.stderr)
            return 1 if problems else 0
        if args.draft:
            if args.version:
                parser.error("--draft takes no version")
            print(draft(args.root))
            return 0
        if not args.version:
            parser.error("give the version (X.Y.Z) or --draft")
        removed = assemble(args.root, args.version, args.date, args.previous)
        print(f"CHANGELOG.md: [{args.version}] - {args.date}; {len(removed)} fragment(s) removed.")
        return 0
    except (ChangelogError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
