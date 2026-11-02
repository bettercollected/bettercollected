"""Promoting a form between workspaces or instances (``bettercollected promote``).

An environment is a workspace: development, staging and production are three
workspaces, each with its own members, API keys and settings. Promotion moves
the form *document* (the form spec) and nothing else, and always as a draft.

This module is the pure part: it makes a pulled document fit another
workspace, the way the product's own copy of a form into a template does, and
says what it changed. It does no network calls and holds no key.

What it changes in the document:

* **Images** from another instance's storage are dropped (the target accepts
  its own storage and Unsplash photos only). Between two workspaces of one
  instance the storage is shared, so the addresses are kept and the target
  has the last word.
* **Option lists** are remapped with a map of list ids (the target has its own
  lists); a list with no entry is dropped. **Options taken from another form's
  answers** are always dropped: that is a decision for the target's staff.
* **Answer patterns** the server cannot run (over 200 characters, lookarounds,
  backreferences) are dropped.
* **"Show answers as choices"** is switched off, **library markers** are
  dropped (they name a section of the source workspace's library) and the
  **logo file** is not carried (a logo is set by uploading it).
* For an **existing target form**, its own retention, purpose, retention note,
  privacy link and identity and editing switches are kept, unless asked
  otherwise: a staging value must not shorten what production keeps.

Whatever the target's server still refuses (a switch it has off, a past
retention date, a question type it lacks) is reported by its own validation.
"""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field
from typing import Any, Mapping
from urllib.parse import urlsplit

# The data-protection keys of ``trust`` an existing target form keeps.
PRIVACY_KEYS = (
    "purpose",
    "retentionText",
    "privacyPolicyUrl",
    "retention",
    "requireVerifiedIdentity",
    "allowEditingResponse",
)

# What never travels, in the words the command prints.
NEVER_COPIED = (
    "responses (answers are never copied)",
    "webhooks, email messages and connections to other systems",
    "who can open the form and who it is shared with",
    "the form's link",
    "when the form is open and its response limit",
    "whether the form is published (the result is always a draft)",
    "the logo file",
)

PATTERN_MAX_LENGTH = 200
# The server runs answer patterns with RE2: no lookaround, no backreferences.
_NOT_RE2 = re.compile(r"\(\?<?[=!]|\\[1-9]|\\k<|\(\?P=")
_UNSPLASH_HOST = "images.unsplash.com"
_BUILTIN_IMAGES = frozenset(
    {
        "https://s3.eu-central-1.wasabisys.com/bettercollected/images/v2_layout_image.webp",
        "https://s3.eu-central-1.wasabisys.com/bettercollected/images/Default_field_image.png",
    }
)


@dataclass
class Report:
    """What normalising changed. Paths and question ids only: never an
    address, a title or any text of the form."""

    images_dropped: list[str] = field(default_factory=list)
    patterns_dropped: list[str] = field(default_factory=list)
    lists_remapped: list[str] = field(default_factory=list)
    lists_dropped: list[str] = field(default_factory=list)
    answer_sources_dropped: list[str] = field(default_factory=list)
    share_as_choices_off: list[str] = field(default_factory=list)
    library_markers_dropped: int = 0
    logo_file_not_copied: bool = False
    trust_kept: list[str] = field(default_factory=list)

    @property
    def adjusted(self) -> bool:
        return bool(
            self.images_dropped
            or self.patterns_dropped
            or self.lists_remapped
            or self.lists_dropped
            or self.answer_sources_dropped
            or self.share_as_choices_off
            or self.library_markers_dropped
            or self.logo_file_not_copied
            or self.trust_kept
        )


def origin(url: str) -> tuple[str, str, int | None]:
    """Scheme, host and port of an address, for "the same instance"."""
    parts = urlsplit(url)
    scheme = (parts.scheme or "").lower()
    try:
        port = parts.port or {"https": 443, "http": 80}.get(scheme)
    except ValueError:
        port = None
    return (scheme, (parts.hostname or "").lower(), port)


def same_instance(source_url: str, target_url: str) -> bool:
    return origin(source_url) == origin(target_url)


def _keeps_image(url: str, shared_storage: bool) -> bool:
    if shared_storage:
        return True
    if url in _BUILTIN_IMAGES:
        return True
    parts = urlsplit(url)
    return parts.scheme == "https" and (parts.hostname or "").lower() == _UNSPLASH_HOST


def _usable_pattern(pattern: Any) -> bool:
    return (
        isinstance(pattern, str)
        and len(pattern.strip()) <= PATTERN_MAX_LENGTH
        and not _NOT_RE2.search(pattern)
    )


def _every_field(fields: Any, path: str):
    """Every question, groups included: ``(question, path)``."""
    for index, item in enumerate(fields or []):
        if not isinstance(item, dict):
            continue
        here = f"{path}/{index}"
        yield item, here
        yield from _every_field(item.get("fields"), f"{here}/fields")


def _drop_images(node: Any, path: str, shared_storage: bool, report: Report) -> None:
    if isinstance(node, dict):
        for key in list(node):
            here = f"{path}/{key}"
            value = node[key]
            if key == "imageUrl" and isinstance(value, str) and value.strip():
                if not _keeps_image(value.strip(), shared_storage):
                    del node[key]
                    report.images_dropped.append(here)
            else:
                _drop_images(value, here, shared_storage, report)
    elif isinstance(node, list):
        for index, item in enumerate(node):
            _drop_images(item, f"{path}/{index}", shared_storage, report)


def normalise(
    document: Mapping[str, Any],
    *,
    shared_storage: bool = False,
    list_map: Mapping[str, str] | None = None,
    keep_target_privacy: bool = False,
) -> tuple[dict, Report]:
    """A copy of ``document`` fit for another workspace, and what changed.

    ``shared_storage``: source and target are workspaces of one instance, so
    image addresses stay. ``list_map`` maps a source option list id to the
    target's. ``keep_target_privacy``: the target form exists, so leave the
    data-protection keys of ``trust`` out of the result (a key left out keeps
    its stored value).
    """
    result = copy.deepcopy(dict(document))
    report = Report()
    list_map = list_map or {}

    _drop_images(result, "", shared_storage, report)

    for page_index, page in enumerate(result.get("pages") or []):
        if not isinstance(page, dict):
            continue
        base = f"/pages/{page_index}/fields"
        for question, path in _every_field(page.get("fields"), base):
            ident = str(question.get("id") or path)
            validations = question.get("validations")
            if isinstance(validations, dict) and "pattern" in validations:
                if not _usable_pattern(validations["pattern"]):
                    del validations["pattern"]
                    report.patterns_dropped.append(ident)
            source = question.get("optionSource")
            if isinstance(source, dict):
                if source.get("kind") == "list":
                    target_id = list_map.get(str(source.get("listId")))
                    if target_id:
                        source["listId"] = target_id
                        report.lists_remapped.append(ident)
                    else:
                        del question["optionSource"]
                        report.lists_dropped.append(ident)
                else:
                    del question["optionSource"]
                    report.answer_sources_dropped.append(ident)
            elif "optionSource" in question:
                del question["optionSource"]
            if question.get("shareAsChoices") is True:
                report.share_as_choices_off.append(ident)
            question.pop("shareAsChoices", None)
            if "library" in question:
                del question["library"]
                report.library_markers_dropped += 1

    logo = result.get("logo")
    if isinstance(logo, dict) and "url" in logo:
        if logo.get("url"):
            report.logo_file_not_copied = True
        del logo["url"]

    trust = result.get("trust")
    if keep_target_privacy and isinstance(trust, dict):
        for key in PRIVACY_KEYS:
            if key in trust:
                del trust[key]
                report.trust_kept.append(key)
        if not trust:
            del result["trust"]
    return result, report


def count_questions(document: Mapping[str, Any]) -> tuple[int, int]:
    """``(pages, questions)`` of a document, groups' questions included."""
    pages = [p for p in document.get("pages") or [] if isinstance(p, dict)]
    return len(pages), sum(
        sum(1 for _ in _every_field(page.get("fields"), "")) for page in pages
    )


def retention_shortened(before: Any, after: Any) -> bool:
    """Whether replacing retention ``before`` with ``after`` can make the
    target delete answers earlier. Unknown shapes count as shortened."""

    def rank(retention: Any) -> tuple[int, Any] | None:
        if not isinstance(retention, dict):
            return None
        kind = retention.get("type")
        if kind == "forever":
            return (2, 0)
        if kind == "days" and isinstance(retention.get("value"), int):
            return (1, retention["value"])
        if kind == "date" and isinstance(retention.get("value"), str):
            return (0, retention["value"])
        return None

    old, new = rank(before), rank(after)
    if before is None or old is None:
        return False  # nothing was kept before, nothing can be shortened
    if after is None or new is None:
        return True
    if new[0] == 2:
        return False  # kept forever
    if old[0] != new[0]:
        return True  # days and an end date do not compare: warn
    return new[1] < old[1]


def render_report(report: Report, out) -> None:
    """The lines ``promote`` prints about what was adjusted and what never
    moves. Counts and question ids only."""

    def line(count: int, what: str, ids: list[str] | None = None, hint: str = "") -> None:
        if not count:
            return
        shown = ""
        if ids:
            head = ", ".join(ids[:5])
            shown = f" ({head}{', ...' if len(ids) > 5 else ''})"
        print(f"  {count} {what}{shown}.{' ' + hint if hint else ''}", file=out)

    if report.adjusted:
        print("Adjusted for the target:", file=out)
        line(
            len(report.images_dropped),
            "image(s) dropped, they are not stored in the target",
            hint="Add them there.",
        )
        line(
            len(report.patterns_dropped),
            "answer pattern(s) dropped, the server cannot run them",
            report.patterns_dropped,
        )
        line(
            len(report.lists_remapped),
            "option list(s) matched to the target's lists",
            report.lists_remapped,
        )
        line(
            len(report.lists_dropped),
            "option list(s) dropped, none given in --list-map",
            report.lists_dropped,
            "Set the question's options in the target.",
        )
        line(
            len(report.answer_sources_dropped),
            "option source(s) taken from another form's answers dropped",
            report.answer_sources_dropped,
        )
        line(
            len(report.share_as_choices_off),
            "question(s) no longer offer their answers as choices",
            report.share_as_choices_off,
        )
        line(report.library_markers_dropped, "reusable-section marker(s) dropped")
        if report.logo_file_not_copied:
            print("  The logo file is not copied. Upload it in the target.", file=out)
        if report.trust_kept:
            print(
                f"  The target form keeps its own {', '.join(report.trust_kept)}"
                " (--copy-privacy copies them).",
                file=out,
            )
    print("Never copied:", file=out)
    for item in NEVER_COPIED:
        print(f"  {item}", file=out)
