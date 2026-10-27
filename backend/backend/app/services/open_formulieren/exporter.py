"""Turn one of our forms into an Open Formulieren import archive.

``build_export(form)`` is pure: a ``StandardForm`` in, the bytes of a zip
out, with a list of everything that did not make the trip. It reads the
tables of ``mapping`` backwards (our question type to the component type, our
comparison to the JSON logic operator), so the importer and the export
cannot drift apart.

What goes in the archive is the structure of the form and nothing else:
pages, questions, choices, answer rules, simple show/hide rules and the
retention days. Never responses or answers, never staff-only (internal)
questions, hidden-field values, secrets, workspace or user ids, e-mail
addresses, logos or addresses of ours. Every string is plain text: markup is
stripped, template delimiters are neutralised, statements are written as
escaped paragraphs. Nothing executable is ever written: no
``customConditional``, no ``calculateValue``, no script of any kind. Rules
are written as data (``conditional`` objects and JSON logic comparisons).

Format facts (entry names, keys, component shapes) are cited in
docs/open-formulieren.md against release 4.0.6; the code is ours.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import html
import io
import json
import re
import unicodedata
import uuid
import zipfile
from dataclasses import dataclass, field
from http import HTTPStatus
from typing import Any, Dict, Iterable, List, Optional, Tuple

from common.models.consent import ResponseRetentionType
from common.models.standard_form import (
    StandardFieldProperty,
    StandardForm,
    StandardFormField,
    is_iso_date,
)

from backend.app.services.open_formulieren import limits
from backend.app.services.open_formulieren.errors import refuse
from backend.app.services.open_formulieren.mapping import (
    ENTRY_DEFINITIONS,
    ENTRY_FORM,
    ENTRY_LOGIC,
    ENTRY_META,
    ENTRY_STEPS,
    ENTRY_VARIABLES,
    REVERSE_COMPARISONS,
    REVERSE_TYPES,
)
from backend.app.services.open_formulieren.text import label_text, plain_text
from backend.app.services.publish_checks import question_text

# the release series this export is written for (the one fixtures and the
# reference instance run; ``limits.ACCEPTED_SERIES`` is what we read back)
EXPORT_RELEASE = "4.0.6"
README_ENTRY = "README.txt"
# the entries of an archive, in the order they are written
EXPORT_ENTRIES = (
    ENTRY_FORM,
    ENTRY_STEPS,
    ENTRY_DEFINITIONS,
    ENTRY_LOGIC,
    ENTRY_VARIABLES,
    ENTRY_META,
    README_ENTRY,
)
# the archive is refused above this many bytes (uncompressed JSON + README):
# far above any real form, well under what our own reader accepts
MAX_EXPORT_BYTES = 4 * 1024 * 1024
MAX_TOTAL_COMPONENT_KEYS = limits.MAX_COMPONENTS

# links in the archive follow their mock-host convention: identifiers only,
# never addresses (forms/utils.py:66-74 at tag 4.0.6)
MOCK_HOST = "http://localhost/api/v2"
_NAMESPACE = uuid.UUID("f3b7a8d2-6c1e-4f0a-9d54-2b8e7c3a1f60")

MAX_LABEL = 500
MAX_NAME = 50  # a form definition's name (their model)
MAX_FORM_NAME = 150
MAX_KEY = 40
MAX_RETENTION_DAYS = 3650
URL_PATTERN = r"^https?://\S+$"
# static variables of their forms: a component key may not shadow them
_RESERVED_KEYS = frozenset(
    {
        "now", "today", "environment", "auth", "auth_type", "auth_bsn", "auth_kvk",
        "auth_pseudo", "auth_context", "language_code", "submission_id", "form",
        "form_name", "form_url", "form_id", "public_reference", "payment",
        "appointment", "price",
    }
)

# our question types that have a component to go to
_TEXT_TYPES = {"short_text", "long_text", "email", "url", "phone_number"}
_PLACEHOLDER_TYPES = {"short_text", "long_text", "email", "url", "phone_number", "number"}


# ------------------------------------------------------------------ report

LEFT_OUT = "left_out"
CHANGED = "changed"


class R:
    """The reasons of the export report (stable; English sentences below)."""

    TYPE = "no_equivalent_question_type"
    CALCULATED = "calculated_field_left_out"
    INTERNAL = "internal_questions_left_out"
    TOO_FEW_CHOICES = "too_few_choices"
    EMPTY_GROUP = "empty_group"
    EMPTY_PAGE = "empty_page"
    JUMPS = "page_jumps_left_out"
    LOGIC_GROUP = "rule_in_repeating_group_left_out"
    LOGIC_SOURCE = "rule_source_left_out"
    LOGIC_LATER = "rule_reads_later_question"
    LOGIC_COMPARISON = "rule_comparison_not_supported"
    LOGIC_VALUE = "rule_value_not_supported"
    LOGIC_GROUP_MODE = "rule_on_group_left_out"
    DATE_RULE = "date_rule_not_carried"
    VALIDATION = "validation_not_carried"
    OTHER_CHOICE = "other_choice_not_carried"
    ATTACHMENT = "image_or_video_not_carried"
    PIPES = "answer_references_became_text"
    FORMATTING = "formatting_removed"
    URL = "link_question_is_text"
    CHECKBOX_REQUIRED = "checkbox_required_not_exported"
    MULTI_DROPDOWN = "multi_select_dropdown"
    MIN_ITEMS = "minimum_items_not_carried"
    ITEM_TITLE = "item_title_not_carried"
    WHY_WE_ASK = "why_we_ask_is_tooltip"
    LABEL = "short_label_not_carried"
    RETENTION = "retention_not_carried"
    HIDDEN_FIELDS = "hidden_fields_left_out"
    CONSENT = "purpose_and_consent_left_out"
    PRIVACY_URL = "privacy_link_left_out"
    ACTIONS = "actions_left_out"


SENTENCES: Dict[str, str] = {
    R.TYPE: "this question type has no equivalent in Open Formulieren ({detail}) and was left out",
    R.CALCULATED: "calculated fields were left out: their formulas are not translated",
    R.INTERNAL: "{detail} staff-only question(s) were left out (they are never exported)",
    R.TOO_FEW_CHOICES: "a choice question needs at least two options there; it was left out",
    R.EMPTY_GROUP: "no question of this repeating group could be exported; the group was left out",
    R.EMPTY_PAGE: "nothing on this page could be exported; the page was left out",
    R.JUMPS: "page jump rules (branching) were left out",
    R.LOGIC_GROUP: "a show/hide rule on a question inside a repeating group (or reading one) was left out",
    R.LOGIC_SOURCE: "a show/hide rule was left out: the question it reads was not exported",
    R.LOGIC_LATER: "a show/hide rule was left out: it reads a question that is not before it",
    R.LOGIC_COMPARISON: "a show/hide rule was left out: its comparison ({detail}) has no equivalent",
    R.LOGIC_VALUE: "a show/hide rule was left out: its value does not fit the question it reads",
    R.LOGIC_GROUP_MODE: "a show/hide rule on a repeating group's items was left out",
    R.DATE_RULE: "a date rule was not carried ({detail})",
    R.VALIDATION: "the answer rule '{detail}' was not carried",
    R.OTHER_CHOICE: "the 'other' option was not carried",
    R.ATTACHMENT: "an image or video attached here was not carried",
    R.PIPES: "answers piped into the text became plain text",
    R.FORMATTING: "text formatting (bold, lists, headings) was removed",
    R.URL: "a link question was exported as a text field with a link pattern",
    R.CHECKBOX_REQUIRED: "'required' was not exported: on a checkbox it would mean 'must be ticked'",
    R.MULTI_DROPDOWN: "a multi-select dropdown was exported as a multi-select list; rules on it were left out",
    R.MIN_ITEMS: "the minimum number of items ({detail}) was not carried; only 'at least one' is",
    R.ITEM_TITLE: "the item title template was not carried",
    R.WHY_WE_ASK: "the 'why we ask' text was exported as the tooltip",
    R.LABEL: "the short label of a date question was not carried",
    R.RETENTION: "the retention setting ({detail}) was not carried: only a number of days is",
    R.HIDDEN_FIELDS: "{detail} hidden URL-parameter field(s) were left out",
    R.CONSENT: "the purpose and consent text were left out (the format has no field for them)",
    R.PRIVACY_URL: "the privacy policy link was left out (it is a global setting there)",
    R.ACTIONS: "on-submit actions were left out (they are never exported)",
}


@dataclass(frozen=True)
class Item:
    kind: str  # LEFT_OUT | CHANGED
    reason: str
    subject: str = ""  # the question's title, or empty for the whole form
    page: Optional[int] = None  # 1-based
    detail: str = ""

    def line(self) -> str:
        where = []
        if self.page:
            where.append(f"page {self.page}")
        if self.subject:
            where.append(f'"{self.subject}"')
        prefix = ", ".join(where) or "form"
        sentence = SENTENCES.get(self.reason, self.reason).format(detail=self.detail)
        return f"- {prefix}: {sentence}"


@dataclass
class ExportResult:
    data: bytes
    items: List[Item]
    pages: int
    questions: int
    logic_rules: int
    filename: str

    @property
    def unmapped(self) -> int:
        """How many things are listed in the README (left out or changed)."""
        return len(self.items)


# -------------------------------------------------------------------- text

_TEMPLATE = re.compile(r"\{([{%#])")
_PIPE = re.compile(r"\{\{\s*(?:field|hidden|group):[^{}]*\}\}")
_BLOCKS = {"paragraph", "heading", "blockquote", "codeBlock", "listItem"}
_FORMATTED_NODES = {"heading", "blockquote", "codeBlock", "bulletList", "orderedList", "horizontalRule"}


def _neutral(text: str) -> str:
    """Template delimiters read literally: their forms render ``{{ }}`` and
    ``{% %}`` in texts, and what we write is plain text."""
    return _TEMPLATE.sub(r"{ \1", text)


def _label(value: Any, limit: int = MAX_LABEL) -> str:
    return _neutral(label_text(value, limit))


def _tv(value: Any) -> Any:
    return getattr(value, "value", value)


def _walk_rich(node: Any, out: List[str], flags: Dict[str, bool], depth: int = 0) -> None:
    if depth > 40 or not isinstance(node, dict):
        return
    kind = node.get("type")
    if kind == "text":
        if node.get("marks"):
            flags["formatted"] = True
        out.append(str(node.get("text") or ""))
        return
    if kind == "hardBreak":
        out.append("\n")
        return
    if kind == "answerPipe":
        flags["piped"] = True
        out.append(str((node.get("attrs") or {}).get("label") or ""))
        return
    if kind in _FORMATTED_NODES:
        flags["formatted"] = True
    block = kind in _BLOCKS
    if block and out and not out[-1].endswith("\n\n"):
        out.append("\n\n")
    for child in node.get("content") or []:
        _walk_rich(child, out, flags, depth + 1)
    if block:
        out.append("\n\n")


def rich_paragraphs(value: Any) -> Tuple[List[str], bool, bool]:
    """``(paragraphs, formatted, piped)`` of a title or statement: a plain
    string or a rich-text document. ``formatted``: marks, headings or lists
    were flattened; ``piped``: an answer reference became its label."""
    flags = {"formatted": False, "piped": False}
    if isinstance(value, str):
        if _PIPE.search(value):
            flags["piped"] = True
            value = _PIPE.sub("…", value)
        text = value
    elif isinstance(value, dict):
        parts: List[str] = []
        _walk_rich(value, parts, flags)
        text = "".join(parts)
    else:
        text = ""
    paragraphs = []
    for chunk in re.split(r"\n\s*\n", text):
        cleaned, _ = plain_text(chunk, limits.MAX_STATEMENT)
        if cleaned:
            paragraphs.append(_neutral(cleaned))
    return paragraphs, flags["formatted"], flags["piped"]


def _slug(text: str, limit: int, fallback: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    slug = "-".join(re.findall(r"[a-z0-9]+", ascii_text.lower()))[:limit].strip("-")
    return slug or fallback


def export_filename(title: Any) -> str:
    """An ASCII-only file name from the form's title (never from anything a
    header could be split by)."""
    base = _slug(label_text(title, 120), 60, "form")
    return f"{base}-open-formulieren.zip"


# ------------------------------------------------------------------- plan


@dataclass
class Planned:
    field: StandardFormField
    key: str
    comp: Dict[str, Any]
    kind: str  # text number date choice yes_no content group file
    order: int
    page: int  # 1-based
    group: Optional["Planned"] = None
    children: List["Planned"] = field(default_factory=list)
    multi: bool = False  # a choice question that takes several answers
    selectboxes: bool = False
    # a token a rule may use (option id, text, label) -> the option's value
    options: Dict[str, str] = field(default_factory=dict)
    col_span: Optional[int] = None
    title: str = ""


class _Unsupported(Exception):
    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(reason)
        self.reason = reason
        self.detail = detail


def _text(value: Any) -> str:
    return value if isinstance(value, str) else ""


def _number(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            number = float(value.strip())
        except ValueError:
            return None
        return number if number == number and abs(number) != float("inf") else None
    return None


def _plain_number(number: float) -> Any:
    return int(number) if number == int(number) else number


class Exporter:
    def __init__(self, form: StandardForm, now: dt.datetime) -> None:
        self.form = form
        self.now = now
        self.title = label_text(form.title, MAX_FORM_NAME) or "Form"
        self.dutch = (form.settings.language if form.settings else None) == "nl"
        self.seed = str(form.form_id or form.title or "form")
        self.items: List[Item] = []
        self._seen: set = set()
        self.by_id: Dict[str, Planned] = {}
        self.keys: set = set()
        self._order = 0
        self._counter = 0
        self.rules: List[Dict[str, Any]] = []
        self.internal_count = 0

    # ---------------------------------------------------------- bookkeeping

    def note(
        self,
        kind: str,
        reason: str,
        subject: str = "",
        page: Optional[int] = None,
        detail: str = "",
        once: bool = False,
    ) -> None:
        item = Item(kind, reason, subject[:120], page, detail[:80])
        marker = (item.kind, item.reason, item.subject, item.page, item.detail)
        if once:
            marker = (item.kind, item.reason, "", None, item.detail)
        if marker in self._seen:
            return
        self._seen.add(marker)
        self.items.append(item)

    def uid(self, *parts: Any) -> str:
        """The same uuid for the same form and the same part, every time."""
        return str(uuid.uuid5(_NAMESPACE, ":".join([self.seed, *map(str, parts)])))

    def _key(self, title: str, fallback: str) -> str:
        words = re.findall(
            r"[A-Za-z0-9]+",
            unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode(),
        )
        base = "".join(w.lower() if i == 0 else w.capitalize() for i, w in enumerate(words))
        base = base[:MAX_KEY] or fallback
        if base[0].isdigit():
            base = f"q{base}"
        if base.lower() in _RESERVED_KEYS or base.lower().startswith("auth_"):
            base = f"{base}Question"
        key, number = base, 2
        while key in self.keys:
            key = f"{base}{number}"
            number += 1
        self.keys.add(key)
        return key

    def _component_id(self, key: str) -> str:
        digest = hashlib.sha1(f"{self.seed}:{key}".encode()).hexdigest()
        return "e" + digest[:6]

    # ----------------------------------------------------------- the plan

    def run(self) -> ExportResult:
        pages = [p for p in self.form.fields or [] if _tv(p.type) == "slide"]
        if not pages and self.form.fields:
            # a form of the first builder holds its questions directly: one page
            pages = [
                StandardFormField(
                    id="page",
                    type="slide",
                    properties=StandardFieldProperty(fields=list(self.form.fields)),
                )
            ]
        planned_pages: List[Tuple[int, str, List[Planned]]] = []
        for number, page in enumerate(pages, start=1):
            props = page.properties
            if props and props.jumps:
                self.note(LEFT_OUT, R.JUMPS, page=number)
            top: List[Planned] = []
            for item in (props.fields if props else None) or []:
                planned = self._plan(item, number, None)
                if planned is not None:
                    top.append(planned)
            if not top:
                self.note(LEFT_OUT, R.EMPTY_PAGE, page=number)
                continue
            title = _label(props.section_title if props else "", MAX_NAME)
            planned_pages.append((number, title, top))
        if self.internal_count:
            self.note(LEFT_OUT, R.INTERNAL, detail=str(self.internal_count))
        if not planned_pages:
            raise refuse(
                "nothing_to_export",
                "No question of this form can be exported.",
                HTTPStatus.UNPROCESSABLE_ENTITY,
            )
        self._logic_pass()
        self._form_notes()
        return self._assemble(planned_pages)

    # -- questions

    def _plan(
        self, item: StandardFormField, page: int, group: Optional[Planned]
    ) -> Optional[Planned]:
        ftype = _tv(item.type)
        if item.internal:
            self.internal_count += 1
            return None
        title = _label(question_text(item))
        subject = title or str(ftype)
        if ftype == "group":
            return self._plan_group(item, page, group, title, subject)
        if ftype == "calculated":
            self.note(LEFT_OUT, R.CALCULATED, subject, page)
            return None
        if ftype not in REVERSE_TYPES and ftype != "url":
            self.note(LEFT_OUT, R.TYPE, subject, page, detail=str(ftype))
            return None
        if ftype == "text":
            return self._plan_statement(item, page, group, title)
        return self._plan_question(item, page, group, title, subject, ftype)

    def _register(self, planned: Planned) -> Planned:
        self._order += 1
        planned.order = self._order
        if planned.field.id:
            self.by_id[planned.field.id] = planned
        return planned

    def _plan_statement(self, item, page, group, title) -> Optional[Planned]:
        source = item.title
        paragraphs, formatted, piped = rich_paragraphs(source)
        if not paragraphs:
            return None
        self._counter += 1
        key = self._key("", f"content{self._counter}")
        body = "".join(
            f"<p>{html.escape(p, quote=False).replace(chr(10), '<br>')}</p>"
            for p in paragraphs
        )
        comp = {
            "id": self._component_id(key),
            "type": "content",
            "key": key,
            "html": body,
            "hidden": False,
            "customClass": "",
            "showInPDF": True,
            "showInEmail": False,
            "showInSummary": False,
            "conditional": {"eq": "", "show": None, "when": ""},
            "openForms": {"translations": {}},
        }
        subject = paragraphs[0][:60]
        if formatted:
            self.note(CHANGED, R.FORMATTING, subject, page)
        if piped:
            self.note(CHANGED, R.PIPES, subject, page)
        if item.attachment or item.image_url:
            self.note(CHANGED, R.ATTACHMENT, subject, page)
        return self._register(
            Planned(item, key, comp, "content", 0, page, group, title=subject,
                    col_span=item.properties.col_span if item.properties else None)
        )

    def _plan_group(self, item, page, group, title, subject) -> Optional[Planned]:
        props = item.properties
        repeat = props.repeat if props else None
        children_in = (props.fields if props else None) or []
        key = self._key(title, "group")
        label = title or "Group"
        if repeat is not None:
            comp: Dict[str, Any] = {
                "id": self._component_id(key),
                "type": "editgrid",
                "key": key,
                "label": label,
                "hidden": False,
                "clearOnHide": True,
                "groupLabel": _label(repeat.item_label, 80) or "Item",
                "saveRow": "Save",
                "removeRow": "Cancel",
                "hideLabel": False,
                "disableAddingRemovingRows": False,
                "description": _description(props.description),
                "tooltip": "",
                "isSensitiveData": False,
                "validate": {
                    "required": repeat.effective_min >= 1,
                    "maxLength": repeat.effective_max,
                },
                "conditional": {"eq": "", "show": None, "when": ""},
                "components": [],
            }
            if repeat.item_title:
                self.note(CHANGED, R.ITEM_TITLE, subject, page)
            if repeat.effective_min > 1:
                self.note(
                    CHANGED, R.MIN_ITEMS, subject, page, detail=str(repeat.effective_min)
                )
        else:
            comp = {
                "id": self._component_id(key),
                "type": "fieldset",
                "key": key,
                "label": label,
                "hidden": False,
                "hideHeader": not title,
                "clearOnHide": True,
                "tooltip": "",
                "conditional": {"eq": "", "show": None, "when": ""},
                "components": [],
            }
        planned = Planned(item, key, comp, "group", 0, page, group, title=title,
                          col_span=props.col_span if props else None)
        self._register(planned)
        for child in children_in:
            made = self._plan(child, page, planned)
            if made is not None:
                planned.children.append(made)
        if not planned.children:
            self.note(LEFT_OUT, R.EMPTY_GROUP, subject, page)
            self.by_id.pop(item.id or "", None)
            self.keys.discard(key)
            return None
        return planned

    def _plan_question(self, item, page, group, title, subject, ftype) -> Optional[Planned]:
        props = item.properties
        rules = item.validations
        required = bool(rules and rules.required)
        key = self._key(title, f"question{self._order + 1}")
        of_type = "textfield" if ftype == "url" else REVERSE_TYPES[ftype]
        kind = {
            "short_text": "text", "long_text": "text", "email": "text", "url": "text",
            "phone_number": "text", "number": "number", "date": "date",
            "yes_no": "yes_no", "multiple_choice": "choice", "dropdown": "choice",
            "file_upload": "file",
        }[ftype]
        comp: Dict[str, Any] = {
            "id": self._component_id(key),
            "type": of_type,
            "key": key,
            "label": title or key,
            "hidden": False,
            "clearOnHide": True,
            "description": _description(props.description if props else None),
            "tooltip": _label(props.why_we_ask if props else "", 1000),
            "validate": {"required": required, "plugins": []},
            "conditional": {"eq": "", "show": None, "when": ""},
            "openForms": {"translations": {}},
            "showInPDF": True,
            "showInEmail": False,
            "showInSummary": True,
            "isSensitiveData": False,
            "translatedErrors": {},
        }
        planned = Planned(item, key, comp, kind, 0, page, group, title=title or key,
                          col_span=props.col_span if props else None)
        _, formatted, piped = rich_paragraphs(item.title)
        if formatted:
            self.note(CHANGED, R.FORMATTING, subject, page)
        if piped or _PIPE.search(_text(props.description if props else "")):
            self.note(CHANGED, R.PIPES, subject, page)
        if props and props.why_we_ask:
            self.note(CHANGED, R.WHY_WE_ASK, subject, page)
        if item.attachment or item.image_url:
            self.note(CHANGED, R.ATTACHMENT, subject, page)
        if props and props.placeholder and ftype in _PLACEHOLDER_TYPES:
            comp["placeholder"] = _label(props.placeholder, 200)
        used: set = {"required"}

        if ftype in ("short_text", "long_text", "url"):
            comp["multiple"] = False
            comp["defaultValue"] = ""
            if rules and rules.max_length:
                comp["validate"]["maxLength"] = int(rules.max_length)
                used.add("max_length")
            pattern = URL_PATTERN if ftype == "url" else None
            if rules and rules.regex and ftype == "short_text":
                pattern = rules.regex
                used.add("regex")
            if pattern:
                comp["validate"]["pattern"] = pattern
            if ftype == "url":
                self.note(CHANGED, R.URL, subject, page)
        elif ftype == "email":
            comp["multiple"] = False
            comp["defaultValue"] = ""
        elif ftype == "phone_number":
            comp["multiple"] = False
            comp["defaultValue"] = ""
        elif ftype == "number":
            comp["defaultValue"] = None
            low, high = (rules.min_value if rules else None), (rules.max_value if rules else None)
            if low is not None:
                comp["validate"]["min"] = _plain_number(float(low))
                used.add("min_value")
            if high is not None:
                comp["validate"]["max"] = _plain_number(float(high))
                used.add("max_value")
        elif ftype == "date":
            comp["defaultValue"] = ""
            comp["multiple"] = False
            comp["datePicker"] = {"minDate": None, "maxDate": None, "showWeeks": True, "startingDay": 1}
            comp["openForms"].update({"minDate": {"mode": ""}, "maxDate": {"mode": ""}})
            self._date_rules(planned, subject, page)
            if props and props.label:
                self.note(CHANGED, R.LABEL, subject, page)
        elif ftype == "yes_no":
            comp["defaultValue"] = False
            if required:
                comp["validate"]["required"] = False
                self.note(CHANGED, R.CHECKBOX_REQUIRED, subject, page)
        elif ftype == "file_upload":
            comp.update(
                {
                    "storage": "url",
                    "url": "",
                    "multiple": False,
                    "useConfigFiletypes": True,
                    "filePattern": "*",
                    "file": {"name": "", "type": [], "allowedTypesLabels": []},
                }
            )
            comp["openForms"]["softRequired"] = False
        else:  # multiple_choice / dropdown
            if not self._choices(planned, item, subject, page, used):
                return None
        # answer rules we have no place for
        for name in ("min_length", "max_length", "min_value", "max_value", "regex", "min_choices", "max_choices"):
            if name in used or not rules:
                continue
            if getattr(rules, name, None) not in (None, ""):
                self.note(CHANGED, R.VALIDATION, subject, page, detail=name)
        return self._register(planned)

    def _choices(self, planned: Planned, item, subject, page, used: set) -> bool:
        props = item.properties
        comp = planned.comp
        ftype = _tv(item.type)
        values: List[Dict[str, str]] = []
        taken: set = set()
        options: Dict[str, str] = {}
        for choice in (props.choices if props else None) or []:
            text = _label(choice.value or choice.label, 300)
            if not text:
                continue
            value = _slug(text, 40, "") or f"option{len(values) + 1}"
            base, number = value, 2
            while value in taken:
                value = f"{base}-{number}"
                number += 1
            taken.add(value)
            values.append({"label": text, "value": value})
            for token in (choice.id, choice.value, choice.label, text):
                if isinstance(token, str) and token:
                    options.setdefault(token, value)
            if choice.attachment:
                self.note(CHANGED, R.ATTACHMENT, subject, page, once=True)
        if len(values) < 2:
            self.note(LEFT_OUT, R.TOO_FEW_CHOICES, subject, page)
            return False
        multi = bool(props and props.allow_multiple_selection)
        planned.options = options
        planned.multi = multi
        if props and props.allow_other_choice:
            self.note(CHANGED, R.OTHER_CHOICE, subject, page)
        rules = item.validations
        comp["openForms"]["dataSrc"] = "manual"
        if ftype == "dropdown":
            comp["type"] = "select"
            comp["data"] = {"values": values}
            comp["multiple"] = multi
            comp["defaultValue"] = [] if multi else ""
            if multi:
                self.note(CHANGED, R.MULTI_DROPDOWN, subject, page, once=False)
        elif multi:
            comp["type"] = "selectboxes"
            comp["values"] = values
            comp["defaultValue"] = {v["value"]: False for v in values}
            planned.selectboxes = True
            if rules and rules.min_choices:
                comp["validate"]["minSelectedCount"] = int(rules.min_choices)
                used.add("min_choices")
            if rules and rules.max_choices:
                comp["validate"]["maxSelectedCount"] = int(rules.max_choices)
                used.add("max_choices")
        else:
            comp["type"] = "radio"
            comp["values"] = values
            comp["defaultValue"] = ""
        return True

    def _date_rules(self, planned: Planned, subject: str, page: int) -> None:
        props = planned.field.properties
        picker = planned.comp["datePicker"]
        config = planned.comp["openForms"]
        taken: set = set()
        for rule in (props.date_rules if props else None) or []:
            side = "min" if rule.comparison in ("after", "on_or_after") else "max"
            if rule.target == "field" or side in taken:
                self.note(
                    CHANGED, R.DATE_RULE, subject, page,
                    detail="another question" if rule.target == "field" else "second limit on one side",
                )
                continue
            taken.add(side)
            if rule.target == "date" and is_iso_date(rule.date):
                day = dt.date.fromisoformat(rule.date)
                # the format's limits include the date itself: a strict
                # rule moves by one day
                if rule.comparison == "after":
                    day += dt.timedelta(days=1)
                elif rule.comparison == "before":
                    day -= dt.timedelta(days=1)
                picker[f"{side}Date"] = f"{day.isoformat()}T00:00:00+00:00"
                config[f"{side}Date"] = {"mode": "fixedValue"}
            elif rule.target == "today":
                config[f"{side}Date"] = {
                    "mode": "future" if side == "min" else "past",
                    "includeToday": rule.comparison.startswith("on_or"),
                }
            else:
                self.note(CHANGED, R.DATE_RULE, subject, page, detail="invalid date")

    # --------------------------------------------------------------- logic

    def _logic_pass(self) -> None:
        for planned in sorted(self.by_id.values(), key=lambda p: p.order):
            logic = planned.field.properties.logic if planned.field.properties else None
            if not logic or not logic.conditions:
                continue
            action = (logic.action or "").upper()
            if action not in ("SHOW", "HIDE"):
                continue
            try:
                self._one_rule(planned, action, (logic.operator or "AND").upper(), logic.conditions)
            except _Unsupported as why:
                self.note(
                    LEFT_OUT, why.reason, planned.title, planned.page, detail=why.detail
                )

    def _one_rule(self, target: Planned, action: str, operator: str, conditions) -> None:
        if target.group is not None:
            raise _Unsupported(R.LOGIC_GROUP)
        if len(conditions) > 10:
            raise _Unsupported(R.LOGIC_COMPARISON, "more than ten conditions")
        parsed: List[Tuple[Planned, str, Any]] = []
        for cond in conditions:
            if cond.group_mode or cond.child_field_id:
                raise _Unsupported(R.LOGIC_GROUP_MODE)
            source = self.by_id.get(cond.field_id or "")
            if source is None:
                raise _Unsupported(R.LOGIC_SOURCE)
            if source.group is not None or source.kind == "group":
                raise _Unsupported(R.LOGIC_GROUP)
            if source.order >= target.order:
                raise _Unsupported(R.LOGIC_LATER)
            parsed.append((source, cond.comparison or "", cond.value))
        if len(parsed) == 1:
            simple = self._simple(parsed[0], action)
            if simple is not None:
                target.comp["conditional"] = simple
                return
        expressions = [self._expression(*p) for p in parsed]
        trigger = expressions[0] if len(expressions) == 1 else {
            "or" if operator == "OR" else "and": expressions
        }
        if action == "SHOW":
            target.comp["hidden"] = True
        self.rules.append(
            {
                "target": target,
                "sources": [p[0] for p in parsed],
                "trigger": trigger,
                "advanced": len(expressions) > 1,
                "state": action == "HIDE",
            }
        )

    def _option(self, source: Planned, value: Any) -> str:
        found = source.options.get(str(value)) if value is not None else None
        if found is None:
            raise _Unsupported(R.LOGIC_VALUE)
        return found

    def _simple(self, parsed: Tuple[Planned, str, Any], action: str) -> Optional[Dict[str, Any]]:
        """The ``conditional`` object for one equality, or None when the
        comparison needs a rule. ``is not`` flips show and hide: showing when
        the answer differs is hiding when it matches."""
        source, comparison, value = parsed
        name = comparison.upper()
        flip = False
        if name == "IS_EQUAL":
            pass
        elif name == "IS_NOT_EQUAL":
            flip = True
        elif source.selectboxes and name in ("CONTAINS", "DOES_NOT_CONTAIN"):
            flip = name == "DOES_NOT_CONTAIN"
        else:
            return None
        if source.kind == "text":
            if not isinstance(value, str) or not value:
                return None
            eq: Any = value
        elif source.kind == "number":
            number = _number(value)
            if number is None:
                return None
            eq = _plain_number(number)
        elif source.kind == "date":
            if not is_iso_date(value):
                return None
            eq = value
        elif source.kind == "yes_no":
            answer = _yes_no(value)
            if answer is None:
                return None
            eq = answer
        elif source.kind == "choice" and (not source.multi or source.selectboxes):
            eq = self._option(source, value)
        else:
            return None
        show = (action == "SHOW") != flip
        return {"show": show, "when": source.key, "eq": eq}

    def _expression(self, source: Planned, comparison: str, value: Any) -> Dict[str, Any]:
        """One comparison as JSON logic data (never evaluated here)."""
        name = comparison.upper()
        var: Dict[str, Any] = {"var": source.key}
        if source.kind == "choice" and source.multi and not source.selectboxes:
            raise _Unsupported(R.LOGIC_COMPARISON, "multi-select dropdown")
        if name in ("IS_EMPTY", "IS_NOT_EMPTY"):
            if source.kind in ("yes_no", "file") or source.selectboxes:
                raise _Unsupported(R.LOGIC_COMPARISON, name.lower())
            empty: Any = None if source.kind == "number" else ""
            return {REVERSE_COMPARISONS["IS_EQUAL" if name == "IS_EMPTY" else "IS_NOT_EQUAL"]: [var, empty]}
        if source.selectboxes:
            if name not in ("IS_EQUAL", "IS_NOT_EQUAL", "CONTAINS", "DOES_NOT_CONTAIN"):
                raise _Unsupported(R.LOGIC_COMPARISON, name.lower())
            option = self._option(source, value)
            chosen = name in ("IS_EQUAL", "CONTAINS")
            return {"==": [{"var": f"{source.key}.{option}"}, chosen]}
        if source.kind == "yes_no":
            answer = _yes_no(value)
            if name not in ("IS_EQUAL", "IS_NOT_EQUAL") or answer is None:
                raise _Unsupported(R.LOGIC_COMPARISON, name.lower())
            return {REVERSE_COMPARISONS[name]: [var, answer]}
        operator = REVERSE_COMPARISONS.get(name)
        if operator is None:
            raise _Unsupported(R.LOGIC_COMPARISON, name.lower())
        if source.kind == "number":
            number = _number(value)
            if number is None:
                raise _Unsupported(R.LOGIC_VALUE)
            return {operator: [var, _plain_number(number)]}
        if name not in ("IS_EQUAL", "IS_NOT_EQUAL"):
            raise _Unsupported(R.LOGIC_COMPARISON, name.lower())
        if source.kind == "choice":
            return {operator: [var, self._option(source, value)]}
        if source.kind == "date":
            if not is_iso_date(value):
                raise _Unsupported(R.LOGIC_VALUE)
            return {operator: [var, value]}
        if source.kind == "text":
            if not isinstance(value, str) or not value:
                raise _Unsupported(R.LOGIC_VALUE)
            return {operator: [var, value]}
        raise _Unsupported(R.LOGIC_COMPARISON, name.lower())

    # --------------------------------------------------------- form notes

    def _form_notes(self) -> None:
        form = self.form
        if form.hidden_fields:
            self.note(LEFT_OUT, R.HIDDEN_FIELDS, detail=str(len(form.hidden_fields)))
        if form.consent:
            self.note(LEFT_OUT, R.CONSENT)
        settings = form.settings
        if settings and settings.privacy_policy_url:
            self.note(LEFT_OUT, R.PRIVACY_URL)
        if form.actions and any(form.actions.values()):
            self.note(LEFT_OUT, R.ACTIONS)
        if settings and settings.response_expiration_type is not None:
            if self._retention_days() is None:
                kind = _tv(settings.response_expiration_type)
                if kind != ResponseRetentionType.FOREVER.value or settings.response_expiration:
                    self.note(LEFT_OUT, R.RETENTION, detail=str(kind))

    def _retention_days(self) -> Optional[int]:
        settings = self.form.settings
        if (
            not settings
            or settings.response_expiration_type != ResponseRetentionType.DAYS
            or not isinstance(settings.response_expiration, str)
            or not settings.response_expiration.strip().isdigit()
        ):
            return None
        days = int(settings.response_expiration.strip())
        return days if 1 <= days <= MAX_RETENTION_DAYS else None

    # ------------------------------------------------------------ assembly

    def _columns(self, top: List[Planned], page: int) -> List[Dict[str, Any]]:
        """The page's components; neighbours with a width below the full
        row are packed into ``columns`` rows of twelve."""
        out: List[Dict[str, Any]] = []
        row: List[Planned] = []
        used = 0

        def flush() -> None:
            nonlocal row, used
            if row:
                key = self._key("", f"columns{page}x{len(out) + 1}")
                out.append(
                    {
                        "id": self._component_id(key),
                        "type": "columns",
                        "key": key,
                        "label": "Columns",
                        "hidden": False,
                        "clearOnHide": True,
                        "conditional": {"eq": "", "show": None, "when": ""},
                        "columns": [
                            {"size": p.col_span, "sizeMobile": 4, "components": [p.comp]}
                            for p in row
                        ],
                    }
                )
            row, used = [], 0

        for planned in top:
            span = planned.col_span
            if span is None or not 1 <= span < 12:
                flush()
                out.append(planned.comp)
                continue
            if used + span > 12:
                flush()
            row.append(planned)
            used += span
        flush()
        return out

    def _assemble(self, planned_pages: List[Tuple[int, str, List[Planned]]]) -> ExportResult:
        form_uuid = self.uid("form")
        form_url = f"{MOCK_HOST}/forms/{form_uuid}"
        steps: List[Dict[str, Any]] = []
        definitions: List[Dict[str, Any]] = []
        step_url_of: Dict[int, str] = {}
        questions = 0
        for _, _, top in planned_pages:
            for planned in _flatten(top):
                if planned.kind == "group":
                    planned.comp["components"] = self._columns(planned.children, planned.page)
        for index, (number, title, top) in enumerate(planned_pages):
            name = title or (f"Pagina {number}" if self.dutch else f"Page {number}")
            definition_uuid = self.uid("definition", number)
            step_uuid = self.uid("step", number)
            slug = f"step-{index + 1}"
            step_url = f"{form_url}/steps/{step_uuid}"
            step_url_of[number] = step_url
            definitions.append(
                {
                    "url": f"{MOCK_HOST}/form-definitions/{definition_uuid}",
                    "uuid": definition_uuid,
                    "name": name,
                    "internal_name": "",
                    "slug": slug,
                    "configuration": {
                        "display": "form",
                        "components": self._columns(top, number),
                    },
                    "login_required": False,
                    "is_reusable": False,
                    "translations": {"nl": {"name": name}, "en": {"name": name}},
                }
            )
            steps.append(
                {
                    "uuid": step_uuid,
                    "index": index,
                    "slug": slug,
                    "form_definition": f"{MOCK_HOST}/form-definitions/{definition_uuid}",
                    "name": name,
                    "internal_name": "",
                    "url": step_url,
                    "is_applicable": True,
                    "login_required": False,
                    "is_reusable": False,
                    "translations": {"nl": {}, "en": {}},
                }
            )
            questions += sum(
                1
                for p in _flatten(top)
                if p.kind not in ("content", "group")
            )
        logic = self._logic_entries(form_url, step_url_of)
        slug = _slug(self.title, 90, "form")
        removal: Dict[str, Any] = {}
        days = self._retention_days()
        if days is not None:
            removal = {
                "successful_submissions_removal_limit": days,
                "successful_submissions_removal_method": "delete_permanently",
            }
        form = {
            "uuid": form_uuid,
            "name": self.title,
            "internal_name": "",
            "internal_remarks": "",
            "login_required": False,
            "translation_enabled": False,
            "registration_backends": [],
            "auth_backends": [],
            "auto_login_authentication_backend": "",
            "payment_required": False,
            "payment_backend": "",
            "payment_backend_options": {},
            "price_variable_key": "",
            "product": None,
            "slug": slug,
            "url": form_url,
            "type": "regular",
            "category": None,
            "theme": None,
            "show_progress_indicator": True,
            "show_summary_progress": False,
            "maintenance_mode": False,
            "active": False,
            "activate_on": None,
            "deactivate_on": None,
            "is_deleted": False,
            "submission_allowed": "yes",
            "submission_limit": None,
            "submission_counter": 0,
            "suspension_allowed": True,
            "ask_privacy_consent": "global_setting",
            "ask_statement_of_truth": "disabled",
            "submissions_removal_options": removal,
            "translations": {"nl": {"name": self.title}, "en": {"name": self.title}},
        }
        meta = {
            "of_release": EXPORT_RELEASE,
            # their own export names the commit it was built from; we are
            # not that build, so the field is left empty
            "of_git_sha": "",
            "created": self.now.isoformat(),
        }
        readme = self._readme(len(steps), questions, len(logic))
        data = _zip(
            {
                ENTRY_FORM: [form],
                ENTRY_STEPS: steps,
                ENTRY_DEFINITIONS: definitions,
                ENTRY_LOGIC: logic,
                ENTRY_VARIABLES: [],
                ENTRY_META: meta,
            },
            readme,
            self.now,
        )
        return ExportResult(
            data=data,
            items=list(self.items),
            pages=len(steps),
            questions=questions,
            logic_rules=len(logic) + sum(
                1 for p in self.by_id.values() if p.comp["conditional"].get("when")
            ),
            filename=export_filename(self.title),
        )

    def _logic_entries(self, form_url: str, step_url_of: Dict[int, str]) -> List[Dict[str, Any]]:
        entries = []
        for number, rule in enumerate(self.rules):
            target: Planned = rule["target"]
            if target.page not in step_url_of:
                continue
            pages = sorted({target.page, *(s.page for s in rule["sources"])})
            rule_uuid = self.uid("rule", number)
            entries.append(
                {
                    "uuid": rule_uuid,
                    "url": f"{MOCK_HOST}/forms/{rule_uuid}/logic-rules",
                    "form": form_url,
                    "json_logic_trigger": rule["trigger"],
                    "description": _label(f"Visibility of {target.title}", 100),
                    "order": number,
                    "actions": [
                        {
                            "uuid": self.uid("action", number),
                            "component": target.key,
                            "form_step_uuid": None,
                            "action": {
                                "type": "property",
                                "property": {"value": "hidden", "type": "bool"},
                                "state": rule["state"],
                            },
                        }
                    ],
                    "is_advanced": rule["advanced"],
                    "form_steps": [step_url_of[p] for p in pages if p in step_url_of],
                }
            )
        return entries

    def _readme(self, pages: int, questions: int, rules: int) -> str:
        left = [i for i in self.items if i.kind == LEFT_OUT]
        changed = [i for i in self.items if i.kind == CHANGED]
        lines = [
            f"Open Formulieren export of: {self.title}",
            f"Made by bettercollected on {self.now.date().isoformat()} "
            f"for Open Formulieren release {EXPORT_RELEASE} (series 4.0).",
            "",
            "What this archive holds",
            f"- {pages} step(s), {questions} question(s), {rules} show/hide rule(s).",
            "- The structure of the form only: pages, questions, options, answer rules,",
            "  simple show/hide rules and the number of days responses are kept.",
            "",
            "What it never holds",
            "- Responses or any answer data, staff-only (internal) questions, URL-parameter",
            "  values, secrets, workspace or user details, logos, addresses of ours, scripts.",
            "- Sign-in, prefill, payment, appointment, registration and e-mail settings, themes,",
            "  welcome and ending pages: set those up in Open Formulieren after importing.",
            "- The imported form is inactive (their import never activates a form).",
            "",
            f"Left out ({len(left)})",
            *(i.line() for i in left),
            *([] if left else ["- nothing"]),
            "",
            f"Changed on the way ({len(changed)})",
            *(i.line() for i in changed),
            *([] if changed else ["- nothing"]),
            "",
            f"Items listed: {len(self.items)}",
            "",
        ]
        return "\n".join(lines)


def _flatten(top: Iterable[Planned]) -> Iterable[Planned]:
    for planned in top:
        yield planned
        yield from _flatten(planned.children)


def _description(value: Any) -> str:
    text = _PIPE.sub("…", value) if isinstance(value, str) else ""
    return _label(text, 1000)


def _yes_no(value: Any) -> Optional[bool]:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower() if value is not None else ""
    if text in ("yes", "true"):
        return True
    if text in ("no", "false"):
        return False
    return None


# -------------------------------------------------------------------- zip


def _json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=True, allow_nan=False).encode("ascii")


def _zip(entries: Dict[str, Any], readme: str, now: dt.datetime) -> bytes:
    """The archive in memory: fixed entry names, deflate, plain files (no
    directories, links or extra attributes), and a size cap."""
    stamp = (max(now.year, 1980), now.month, now.day, now.hour, now.minute, now.second)
    blobs = [(name, _json(value)) for name, value in entries.items()]
    blobs.append((README_ENTRY, readme.encode("utf-8")))
    if sum(len(b) for _, b in blobs) > MAX_EXPORT_BYTES:
        raise refuse(
            "export_too_large",
            "This form is too large to export.",
            HTTPStatus.UNPROCESSABLE_ENTITY,
        )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, blob in blobs:
            info = zipfile.ZipInfo(name, date_time=stamp)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o644 << 16
            archive.writestr(info, blob)
    return buffer.getvalue()


def build_export(form: StandardForm, now: Optional[dt.datetime] = None) -> ExportResult:
    """The archive of ``form`` and what could not be carried over, or
    ``ImportRefused`` (nothing to export, too large)."""
    when = (now or dt.datetime.now(dt.timezone.utc)).replace(microsecond=0)
    return Exporter(form, when).run()
