"""Making a form spec document fit another workspace: the step before the spec
writer in a promotion (copying a form to another workspace).

Pure: a document in, a document and a report out. No query, no network call, no
user. The caller hands in what only the server knows (the image rule, the
pattern rule and the map from the source workspace's option lists to the
target's), so the cases of this module can be run as a table.

What it changes, in the same way a copy of a form into a template does
(``WorkspaceFormService.duplicate_form``):

* **Images** that are not first-party (our storage, Unsplash through our route,
  the built-in two) are dropped; a first-party address stays (it is spelled in
  its canonical form).
* **Option lists** are matched by *name*: a question whose list the target has
  under the same name points at the target's list; one without a match loses
  its source (its fixed choices stay). Lists never move. **Options taken from
  another form's answers** are always dropped: that decision belongs to the
  target's staff.
* **Answer patterns** the server cannot run are dropped.
* **"Show answers as choices"** is switched off and **library markers** are
  dropped (they name a section of the source workspace's library).
* The **logo file** is not carried (a logo is set by uploading it).
* For an **existing target form** the data-protection keys of ``trust`` are
  left out (a key a replace leaves out keeps its stored value), unless the
  caller ticked to copy them.

Everything it changes is counted in the report; the report holds question ids
and counts, never an address, a title or a text of the form.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterator, List, Mapping, Optional, Tuple

# The trust keys an existing target form keeps (document keys, as in the spec).
PRIVACY_KEYS = (
    "purpose",
    "retentionText",
    "privacyPolicyUrl",
    "retention",
    "requireVerifiedIdentity",
    "allowEditingResponse",
)

ImageRule = Callable[[str], Optional[str]]
PatternRule = Callable[[str], bool]


@dataclass
class Report:
    images_dropped: int = 0
    patterns_dropped: List[str] = field(default_factory=list)
    lists_remapped: List[str] = field(default_factory=list)
    lists_dropped: List[str] = field(default_factory=list)
    answer_sources_dropped: List[str] = field(default_factory=list)
    share_as_choices_off: List[str] = field(default_factory=list)
    library_markers_dropped: int = 0
    logo_file_not_copied: bool = False
    trust_kept: List[str] = field(default_factory=list)

    def counts(self) -> Dict[str, int]:
        """What was adjusted, as counts (the shape kept on the target form and in
        the audit entry's total): only the kinds that happened."""
        values = {
            "imagesDropped": self.images_dropped,
            "patternsDropped": len(self.patterns_dropped),
            "listsMatchedByName": len(self.lists_remapped),
            "listsNotFound": len(self.lists_dropped),
            "answerSourcesDropped": len(self.answer_sources_dropped),
            "shareAsChoicesOff": len(self.share_as_choices_off),
            "libraryMarkersDropped": self.library_markers_dropped,
            "logoFileNotCopied": int(self.logo_file_not_copied),
            "dataProtectionKept": len(self.trust_kept),
        }
        return {key: value for key, value in values.items() if value}

    def to_dict(self) -> Dict[str, Any]:
        """The report as the preview answers it: counts, and the question ids
        the question-level changes concern."""
        return {
            "counts": self.counts(),
            "patternsDropped": list(self.patterns_dropped),
            "listsMatchedByName": list(self.lists_remapped),
            "listsNotFound": list(self.lists_dropped),
            "answerSourcesDropped": list(self.answer_sources_dropped),
            "shareAsChoicesOff": list(self.share_as_choices_off),
            "trustKept": list(self.trust_kept),
        }


def every_question(fields: Any, path: str) -> Iterator[Tuple[dict, str]]:
    """Every question of a list of fields, group children included:
    ``(question, JSON pointer)``."""
    for index, item in enumerate(fields or []):
        if not isinstance(item, dict):
            continue
        here = f"{path}/{index}"
        yield item, here
        yield from every_question(item.get("fields"), f"{here}/fields")


def option_list_ids(document: Mapping[str, Any]) -> List[str]:
    """The ids of the workspace option lists the document's questions use, in
    order, each once."""
    found: Dict[str, None] = {}
    for page in document.get("pages") or []:
        if not isinstance(page, dict):
            continue
        for question, _ in every_question(page.get("fields"), ""):
            source = question.get("optionSource")
            if isinstance(source, dict) and source.get("kind") == "list":
                list_id = source.get("listId")
                if isinstance(list_id, str) and list_id:
                    found.setdefault(list_id, None)
    return list(found)


def _fix_images(node: Any, image_rule: ImageRule, report: Report) -> None:
    if isinstance(node, dict):
        for key in list(node):
            value = node[key]
            if key == "imageUrl" and isinstance(value, str) and value.strip():
                kept = image_rule(value)
                if kept is None:
                    del node[key]
                    report.images_dropped += 1
                elif kept != value:
                    node[key] = kept
            else:
                _fix_images(value, image_rule, report)
    elif isinstance(node, list):
        for item in node:
            _fix_images(item, image_rule, report)


def normalise(
    document: Mapping[str, Any],
    *,
    image_rule: ImageRule,
    pattern_ok: PatternRule,
    list_map: Optional[Mapping[str, str]] = None,
    keep_target_privacy: bool = False,
) -> Tuple[Dict[str, Any], Report]:
    """A copy of ``document`` fit for another workspace, and what changed.

    ``image_rule``: the kept (canonical) spelling of a first-party image address,
    None for any other. ``pattern_ok``: whether the server can run the pattern.
    ``list_map``: the source workspace's option list id to the target's list of
    the same name; a list with no entry is dropped. ``keep_target_privacy``: the
    target form exists, so its data-protection keys are left out of the result."""
    result = copy.deepcopy(dict(document))
    report = Report()
    list_map = list_map or {}

    _fix_images(result, image_rule, report)

    for page_index, page in enumerate(result.get("pages") or []):
        if not isinstance(page, dict):
            continue
        base = f"/pages/{page_index}/fields"
        for question, path in every_question(page.get("fields"), base):
            ident = str(question.get("id") or path)
            validations = question.get("validations")
            if isinstance(validations, dict) and isinstance(
                validations.get("pattern"), str
            ):
                if not pattern_ok(validations["pattern"]):
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
