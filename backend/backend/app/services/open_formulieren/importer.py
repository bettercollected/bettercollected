"""Turn a decoded Open Formulieren export into a draft form.

``build_draft(archive)`` plans every step and component (pure data in, plain
values out), builds the form through the edit operations (``apply_form_ops``)
in memory, and returns the form with a report of everything that was dropped,
changed or flagged. Nothing is saved here, and nothing from the file is
executed, evaluated or rendered (see ``logic`` for the rules, ``text`` for the
strings).
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from http import HTTPStatus
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlsplit

from common.models.standard_form import (
    REPEAT_CHILD_FIELD_TYPES,
    LayoutType,
    StandardForm,
    StandardFormSettings,
    ThankYouPageField,
    WelcomePageField,
    is_iso_date,
)
from common.models.consent import ResponseRetentionType
from common.form_spec.models import MAX_FIELDS, MAX_PAGES, checked_pattern
from pydantic import ValidationError

from backend.app.constants.themes import new_form_theme
from backend.app.services.ai.ops import FormOps, OpResult, apply_form_ops
from backend.app.services.answer_validation import compile_pattern
from backend.app.services.open_formulieren import limits
from backend.app.services.open_formulieren import report as R
from backend.app.services.open_formulieren.archive import Archive
from backend.app.services.open_formulieren import budget
from backend.app.services.open_formulieren import variables as V
from backend.app.services.open_formulieren.numbers import as_plain, to_int, to_number
from backend.app.services.open_formulieren.errors import ImportRefused, refuse, unexpected
from backend.app.services.open_formulieren.logic import (
    Cond,
    Rule,
    Trigger,
    Unsupported,
    combine,
    decide,
    parse_trigger,
    simple_conditional,
    translate,
)
from backend.app.services.open_formulieren.mapping import (
    ADDITION_MAX_LENGTH,
    ADDITION_PATTERN,
    ADDRESS_DERIVED_PARTS,
    ADDRESS_FALLBACK_LABEL,
    ADDRESS_PARTS,
    ADDRESS_TYPE,
    CHOICE_TYPES,
    GROUP_TYPES,
    HOUSE_NUMBER_PATTERN,
    LAYOUT_TYPES,
    POSTCODE_PATTERN,
    SCRIPT_KEYS,
    SILENT_TYPES,
    TIME_PATTERN,
    TYPE_RULES,
    UNSUPPORTED_TYPES,
    Reason,
    TypeRule,
)
from backend.app.services.open_formulieren.report import Report
from backend.app.services.open_formulieren.text import label_text, plain_text
from backend.app.services.publish_checks import (
    ID_NUMBER_CANDIDATE_TYPES,
    ID_NUMBER_TITLE,
)

MAX_RETENTION_DAYS = 3650
_NATIONAL_ID_PREFILL = ("bsn", "burgerservicenummer")


# ----------------------------------------------------------------- the plan


@dataclass
class Question:
    """One question (or statement, or repeating group) to create."""

    key: Optional[str]  # the component key; None for a generated question
    of_type: str
    rule: TypeRule
    label: str
    order: int
    page: int
    ref: str
    spec: Dict[str, Any]
    group: Optional["Question"] = None
    validation: Dict[str, Any] = field(default_factory=dict)
    date_rules: List[Dict[str, Any]] = field(default_factory=list)
    choices: Dict[str, str] = field(default_factory=dict)  # option value -> text
    chain: List[Rule] = field(default_factory=list)
    children: List["Question"] = field(default_factory=list)
    is_group: bool = False
    group_spec: Dict[str, Any] = field(default_factory=dict)
    # set when the question failed to be created
    failed: bool = False
    # one of several questions made from one component (an address): the
    # component's own key and label, which a report names, and what the
    # questions share, so that a report about them is written once
    origin_key: Optional[str] = None
    origin_label: Optional[str] = None
    unit: Optional[int] = None
    # the component holds a list of values (``multiple``)
    multiple: bool = False
    # its value starts from a default, or is filled by a prefill or a script
    # of the file: none of which we carry (a calculation reading it would
    # differ from the original's)
    default_value: bool = False
    rewritten: bool = False
    # a rule, a condition, an enclosing layout component or its step can hide
    # it (the original then clears its value; a calculation here would not)
    conditional: bool = False
    # the id the form gave the question once it was created
    field_id: Optional[str] = None


@dataclass
class Page:
    index: int  # step position in the source, 0-based
    title: str
    items: List[Question] = field(default_factory=list)


@dataclass
class Built:
    form: StandardForm
    report: Report
    summary: Dict[str, int]
    title: str


_int = to_int
_number = to_number


def _has_default(value: Any) -> bool:
    """Whether a component's default answer holds anything (an object of
    unticked boxes does not)."""
    if isinstance(value, dict):
        return any(_has_default(v) for v in value.values())
    if isinstance(value, list):
        return any(_has_default(v) for v in value)
    if isinstance(value, bool):
        return value
    return value not in (None, "", 0)


def _field_cap() -> int:
    """How many questions one import may create."""
    return min(MAX_FIELDS, limits.MAX_IMPORT_FIELDS)


def anchored(pattern: str) -> str:
    """The pattern as Open Formulieren applies it: to the whole answer. Their
    validation adds a leading ``^`` and a trailing ``$`` when the pattern lacks
    one (``formio/components/utils.py:6-14`` at 4.0.6, used by the text
    components at ``vanilla.py:130-136``, ``336-342`` and ``custom.py:389``,
    ``1173``), so a pattern is a full match there. Ours search the answer, so
    a pattern that is not anchored at both ends is wrapped to mean the same."""
    pattern = pattern.strip()
    if pattern.startswith("^") and pattern.endswith("$"):
        return pattern
    return f"^(?:{pattern})$"


def _dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _help_set(form: Dict[str, Any]) -> bool:
    """Whether the form has help of its own. 4.0 exports always write both
    help objects, empty when unused, so their presence alone says nothing.
    The dialog's content and image are the form's; the callout's content and
    image come from the instance's global settings, so only its ``display``
    (``never`` unless shown before or after the start page) is the form's."""
    dialog = _dict(form.get("help_dialog"))
    content = dialog.get("content")
    if (isinstance(content, str) and content.strip()) or dialog.get("image"):
        return True
    return _dict(form.get("help_callout_page")).get("display") in (
        "before_start_page",
        "after_start_page",
    )


def _last_segment(url: Any) -> str:
    """The id at the end of a link to a resource of the source instance. The
    link is only ever read for that id: never fetched, never used as an
    address."""
    if not isinstance(url, str):
        return ""
    return urlsplit(url).path.rstrip("/").rsplit("/", 1)[-1]


def _language_of(top: Any, translations: Any, name: str) -> Optional[str]:
    """``nl`` or ``en`` when the text an export wrote at the top level is the
    text of that language's translation and not of the other one. An export
    writes the text of the language it was made in at the top level and keeps
    both languages under ``translations`` (nothing else says which one is
    which), so this is how the language of the texts shows."""
    text = label_text(top, 200)
    if not text:
        return None
    found = _dict(translations)
    dutch = label_text(_dict(found.get("nl")).get(name), 200)
    english = label_text(_dict(found.get("en")).get(name), 200)
    if text == dutch and text != english:
        return "nl"
    if text == english and text != dutch:
        return "en"
    return None


def archive_language(archive: Archive) -> str:
    """The language the archive's texts are written in, ``en`` or ``nl``: the
    one most of its names (the form's and its definitions') are in. English
    when they do not say (one language only, or the two texts alike)."""
    votes = [
        _language_of(
            archive.form.get("name"), archive.form.get("translations"), "name"
        )
    ]
    for definition in archive.definitions[: limits.MAX_STEPS]:
        votes.append(
            _language_of(
                _dict(definition).get("name"),
                _dict(definition).get("translations"),
                "name",
            )
        )
    return "nl" if votes.count("nl") > votes.count("en") else "en"


def _component_language(comp: Dict[str, Any]) -> Optional[str]:
    """The language of one component's label, when its own translations say."""
    return _language_of(
        comp.get("label"), _dict(comp.get("openForms")).get("translations"), "label"
    )


class Planner:
    """Walks the steps and components and plans the questions."""

    def __init__(self, archive: Archive, report: Report) -> None:
        self.archive = archive
        self.report = report
        self.pages: List[Page] = []
        self.by_key: Dict[str, Question] = {}
        self.seen_keys: set = set()
        self.logic: Dict[str, List[Tuple[Trigger, bool]]] = {}
        self._order = 0
        self._components = 0
        self._refs = 0
        self.page_index = 0
        self.language = archive_language(archive)
        self._address_keys: set = set()
        self._address_counts: Dict[str, int] = {}
        self._units = 0
        self._reported: set = set()
        # questions planned so far, counted as the form's size check counts
        # them (a repeating group twice: as an item and as a group)
        self._planned = 0
        # logic rules in the order they apply, the user-defined variables of
        # the file and what is known of them (``variables.analyse``), the
        # rules only a variable's calculation needs (reported if it is not
        # carried after all), and the ids the form gave the pages
        self.rules: List[Dict[str, Any]] = []
        self.variables: Dict[str, V.Info] = {}
        self.deferred: List[int] = []
        self.written: set = set()
        # components a rule can show or hide, steps a rule can make (not)
        # applicable, and how many enclosing layout components can be hidden
        self.hide_keys: set = set()
        self.step_keys: set = set()
        self._hideable_parents = 0
        self._step_hideable = False
        self.page_ids: Dict[str, str] = {}

    # --------------------------------------------------------- reporting

    def note(
        self,
        code: str,
        reason: str,
        severity: str = R.WARNING,
        *,
        key: Any = None,
        label: Any = None,
        detail: Optional[Dict[str, Any]] = None,
        flag: Optional[str] = None,
        once: bool = False,
        step: Optional[int] = -1,
        kind: str = R.COMPONENT,
    ) -> None:
        self.report.add(
            code,
            kind,
            reason,
            severity,
            key=key,
            label=label,
            step=self.page_index if step == -1 else step,
            flag=flag,
            detail=detail,
            once=once,
        )

    # ------------------------------------------------------------- logic

    def read_logic(self) -> None:
        """The rules that show or hide a component, by target. Everything
        else a rule does is reported and ignored, except the rule that only
        sets a variable that becomes a calculated question (``variables``)."""
        self.rules = sorted(
            self.archive.logic,
            key=lambda r: r.get("order") if isinstance(r.get("order"), int) else 0,
        )
        self.variables = V.analyse(self.archive.variables, self.rules, self.archive.is_3x)
        self.written = V.written_keys(self.archive.variables, self.rules)
        self.hide_keys = V.hide_targets(self.rules)
        self.step_keys = V.step_targets(self.rules)
        consumed = V.consumed_rules(self.rules, self.variables)
        for index, rule in enumerate(self.rules):
            if index in consumed:
                # reported later when its variable is not carried after all
                self.deferred.append(index)
                continue
            self.read_rule(index)

    def read_rule(self, index: int) -> None:
        rule = self.rules[index]
        name = f"rule-{index + 1}"
        label = rule.get("description")
        # 3.x only: a rule of a form still on the old logic evaluation may
        # only start once a given step is reached. Ours is checked
        # wherever the answers are, so the rule would act earlier than
        # the original: dropped, not guessed.
        if self.archive.is_3x and rule.get("trigger_from_step"):
            self.note(
                R.DROPPED, Reason.TRIGGER, kind=R.LOGIC, key=name, label=label,
                step=None, detail={"cause": "trigger_from_step"},
            )
            return
        try:
            trigger = parse_trigger(rule.get("json_logic_trigger"))
        except Unsupported as why:
            self.note(
                R.DROPPED, why.reason, kind=R.LOGIC, key=name, label=label, step=None
            )
            return
        for action in _list(rule.get("actions")):
            self._read_action(name, label, trigger, _dict(action))

    def _read_action(
        self, name: str, label: Any, trigger: Trigger, action: Dict[str, Any]
    ) -> None:
        body = _dict(action.get("action"))
        kind = body.get("type")
        target = action.get("component")
        if kind == "property":
            prop = _dict(body.get("property"))
            state = body.get("state")
            if (
                prop.get("value") == "hidden"
                and isinstance(state, bool)
                and isinstance(target, str)
                and target
            ):
                self.logic.setdefault(target, []).append((trigger, state))
                return
            self.note(
                R.DROPPED,
                Reason.ACTION,
                kind=R.LOGIC,
                key=name,
                label=label,
                step=None,
                detail={
                    "actionType": "property",
                    "property": prop.get("value") if isinstance(prop.get("value"), str) else "",
                },
            )
            return
        self.note(
            R.DROPPED,
            Reason.ACTION,
            kind=R.LOGIC,
            key=name,
            label=label,
            step=None,
            detail={"actionType": kind if isinstance(kind, str) else ""},
        )

    def unmatched_targets(self) -> None:
        for target in self.logic:
            if target not in self.seen_keys:
                self.note(
                    R.DROPPED,
                    Reason.TARGET_MISSING,
                    kind=R.LOGIC,
                    key=target,
                    step=None,
                )

    # ------------------------------------------------------------- steps

    def plan(self) -> None:
        self.read_logic()
        definitions = {
            d.get("uuid"): d for d in self.archive.definitions if isinstance(d.get("uuid"), str)
        }
        steps = sorted(
            self.archive.steps,
            key=lambda s: s.get("index") if isinstance(s.get("index"), int) else 0,
        )
        for position, step in enumerate(steps):
            self.page_index = position
            definition = definitions.get(_last_segment(step.get("form_definition")))
            configuration = _dict(
                definition.get("configuration") if definition else step.get("configuration")
            )
            title = label_text(
                step.get("name") or (definition or {}).get("name"), limits.MAX_TITLE
            )
            page = Page(position, title)
            step_uuid = step.get("uuid")
            self._step_hideable = (
                step.get("is_applicable") is False
                or "" in self.step_keys
                or (isinstance(step_uuid, str) and step_uuid in self.step_keys)
            )
            self.walk(_list(configuration.get("components")), page, [], None, 0)
            if page.items:
                self.pages.append(page)
            else:
                self.note(
                    R.DROPPED, Reason.EMPTY_STEP, R.INFO, label=title or None, kind=R.COMPONENT
                )
        self.unmatched_targets()

    # --------------------------------------------------------- components

    def _mark_seen(self, comp: Dict[str, Any]) -> None:
        """The keys inside a component that is dropped as a whole, so rules
        that name them are not reported as pointing at nothing."""
        stack = [comp]
        while stack:
            item = stack.pop()
            if isinstance(item.get("key"), str):
                self.seen_keys.add(item["key"])
            for child in _list(item.get("components")):
                if isinstance(child, dict):
                    stack.append(child)
            for column in _list(item.get("columns")):
                for child in _list(_dict(column).get("components")):
                    if isinstance(child, dict):
                        stack.append(child)

    def _next_ref(self, prefix: str) -> str:
        self._refs += 1
        return f"{prefix}{self._refs}"

    def _scripts(self, comp: Dict[str, Any], key: Any, label: Any) -> None:
        """Code in a component's definition is never run or kept: it is
        noticed (by being present) and reported."""
        found = [k for k in SCRIPT_KEYS if comp.get(k)]
        validate = _dict(comp.get("validate"))
        if validate.get("custom"):
            found.append("validate.custom")
        if _list(comp.get("logic")):
            found.append("logic")
        for name in found:
            self.note(
                R.DROPPED,
                Reason.CUSTOM_SCRIPT,
                key=key,
                label=label,
                detail={"property": name},
            )

    def walk(
        self,
        components: List[Any],
        page: Page,
        chain: List[Rule],
        group: Optional[Question],
        depth: int,
        col_span: Optional[int] = None,
    ) -> None:
        if depth > limits.MAX_COMPONENT_DEPTH:
            raise refuse(
                "archive_too_complex",
                "The form nests components too deeply.",
                HTTPStatus.UNPROCESSABLE_ENTITY,
            )
        for comp in components:
            if not isinstance(comp, dict):
                continue
            budget.check()
            self._components += 1
            if self._components > limits.MAX_COMPONENTS:
                raise refuse(
                    "archive_too_complex",
                    "The form has more components than can be imported.",
                    HTTPStatus.UNPROCESSABLE_ENTITY,
                )
            self.component(comp, page, chain, group, depth, col_span)

    def component(
        self,
        comp: Dict[str, Any],
        page: Page,
        chain: List[Rule],
        group: Optional[Question],
        depth: int,
        col_span: Optional[int],
    ) -> None:
        of_type = comp.get("type") if isinstance(comp.get("type"), str) else ""
        key = comp.get("key") if isinstance(comp.get("key"), str) else None
        if key:
            self.seen_keys.add(key)
        label = label_text(comp.get("label"), limits.MAX_TITLE)
        if of_type in SILENT_TYPES:
            return
        self._scripts(comp, key, label or None)

        if of_type in UNSUPPORTED_TYPES:
            self.note(
                R.DROPPED,
                Reason.UNSUPPORTED_TYPE,
                key=key,
                label=label,
                detail={"componentType": of_type},
            )
            return
        if (
            of_type != ADDRESS_TYPE
            and of_type not in TYPE_RULES
            and of_type not in LAYOUT_TYPES | GROUP_TYPES
        ):
            self.note(
                R.DROPPED,
                Reason.UNKNOWN_TYPE,
                key=key,
                label=label,
                detail={"componentType": of_type[:60]},
            )
            return

        decision = decide(
            comp.get("hidden") is True,
            simple_conditional(comp.get("conditional")),
            self.logic.get(key or "", []),
        )
        if decision.always_hidden:
            self._mark_seen(comp)
            self.note(
                R.DROPPED,
                Reason.ALWAYS_HIDDEN,
                R.INFO,
                key=key,
                label=label,
                detail={"componentType": of_type},
            )
            return
        if decision.problem:
            self.note(R.DROPPED, decision.problem, kind=R.LOGIC, key=key, label=label)
        for problem in decision.conflicts:
            self.note(R.DROPPED, problem, kind=R.LOGIC, key=key, label=label)
        own = chain + ([decision.rule] if decision.rule else [])
        # whether a condition, a rule or ``hidden`` can hide this component,
        # and with it everything inside it (``Question.conditional``)
        hideable = (
            V.has_conditional(comp.get("conditional"))
            or comp.get("hidden") is True
            or bool(key and key in self.hide_keys)
            or "" in self.hide_keys
        )
        self._hideable_parents += 1 if hideable else 0
        try:
            self._dispatch(comp, of_type, page, own, group, depth, key, label, col_span)
        finally:
            self._hideable_parents -= 1 if hideable else 0

    def _dispatch(
        self, comp, of_type, page, own, group, depth, key, label, col_span
    ) -> None:
        if of_type == "fieldset":
            self._fieldset(comp, page, own, group, depth, key, label, col_span)
            return
        if of_type == "columns":
            for column in _list(comp.get("columns")):
                column = _dict(column)
                size = _int(column.get("size"))
                span = size if size is not None and 1 <= size <= 12 else None
                self.walk(_list(column.get("components")), page, own, group, depth + 1, span)
            return
        if of_type in GROUP_TYPES:
            if group is not None:
                self.note(
                    R.DROPPED,
                    Reason.NOT_IN_GROUP,
                    key=key,
                    label=label,
                    detail={"componentType": of_type},
                )
                return
            self._editgrid(comp, page, own, depth, key, label, col_span)
            return
        if of_type == ADDRESS_TYPE:
            self._address(comp, page, own, group, key, label, col_span)
            return
        self._question(comp, of_type, page, own, group, key, label, col_span)

    # -- layout and groups

    def _fieldset(self, comp, page, chain, group, depth, key, label, col_span) -> None:
        if label and comp.get("hideHeader") is not True:
            heading = self._make(
                None, "content", TYPE_RULES["content"], label, page, group,
                {"title": label[: limits.MAX_STATEMENT], "type": "text"},
            )
            heading.chain = list(chain)
            if group is not None:
                group.children.append(heading)
            else:
                page.items.append(heading)
            self._planned += 1
        self.walk(_list(comp.get("components")), page, chain, group, depth + 1, col_span)

    def _editgrid(self, comp, page, chain, depth, key, label, col_span) -> None:
        validate = _dict(comp.get("validate"))
        maximum = _int(validate.get("maxLength"))
        maximum = min(max(maximum, 1), 50) if maximum else 10
        minimum = min(1 if validate.get("required") is True else 0, maximum)
        item_label = label_text(comp.get("groupLabel"), 80) or "Item"
        title = label or key or "Group"
        group = self._make(
            key, "editgrid", TYPE_RULES["textfield"], title, page, None, {}
        )
        group.is_group = True
        group.chain = list(chain)
        group.group_spec = {
            "title": title,
            "itemLabel": item_label,
            "minItems": minimum,
            "maxItems": maximum,
        }
        description = label_text(comp.get("description"), limits.MAX_HELP)
        if description:
            group.group_spec["description"] = description
        self.walk(_list(comp.get("components")), page, chain, group, depth + 1, None)
        if not group.children:
            self.note(R.DROPPED, Reason.EMPTY_GROUP, key=key, label=label)
            self.by_key.pop(key or "", None)
            return
        page.items.append(group)
        self._planned += 2

    # -- one question

    def _make(
        self, key, of_type, rule, label, page, group, spec, register: bool = True
    ) -> Question:
        self._order += 1
        question = Question(
            key=key,
            of_type=of_type,
            rule=rule,
            label=label,
            order=self._order,
            page=page.index,
            ref=self._next_ref("q"),
            spec=spec,
            group=group,
        )
        if register and key and key not in self.by_key:
            self.by_key[key] = question
        spec["ref"] = question.ref
        return question

    def _choices(self, comp, of_type, key, label) -> Optional[Tuple[Dict[str, str], List[str]]]:
        source = _dict(comp.get("openForms")).get("dataSrc")
        if isinstance(source, str) and source not in ("", "manual"):
            self.note(
                R.DROPPED,
                Reason.CHOICES_FROM_VARIABLE,
                key=key,
                label=label,
                detail={"source": source[:40]},
            )
            return None
        raw = (
            _list(_dict(comp.get("data")).get("values"))
            if of_type == "select"
            else _list(comp.get("values"))
        )
        by_value: Dict[str, str] = {}
        texts: List[str] = []
        used: set = set()
        counts: Dict[str, int] = {}
        for option in raw[: limits.MAX_CHOICES + 1]:
            option = _dict(option)
            value = option.get("value")
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                value = str(value)
            if not isinstance(value, str):
                continue
            text = label_text(option.get("label"), limits.MAX_CHOICE) or label_text(
                value, limits.MAX_CHOICE
            )
            if not text or value in by_value:
                continue
            # distinct texts: a set and a counter per text (no list scans)
            base = text
            if text in used:
                counts[base] = counts.get(base, 1) + 1
                text = f"{base} ({counts[base]})"
                while text in used:
                    counts[base] += 1
                    text = f"{base} ({counts[base]})"
            used.add(text)
            by_value[value] = text
            texts.append(text)
        if len(texts) > limits.MAX_CHOICES:
            self.note(R.DROPPED, Reason.REJECTED, key=key, label=label, detail={"why": "too many options"})
            return None
        if len(texts) < 2:
            self.note(R.DROPPED, Reason.TOO_FEW_CHOICES, key=key, label=label)
            return None
        return by_value, texts

    def _question(self, comp, of_type, page, chain, group, key, label, col_span) -> None:
        rule = TYPE_RULES[of_type]
        title = label or key or "Untitled question"
        if of_type == "content":
            text, markup = plain_text(comp.get("html"), limits.MAX_STATEMENT)
            if not text:
                return
            if markup:
                self.note(R.CHANGED, Reason.HTML_SIMPLIFIED, R.INFO, key=key)
            question = self._make(
                key, of_type, rule, text[:80], page, group,
                {"title": text, "type": "text"},
            )
            question.chain = list(chain)
            self._place(question, page, group)
            return

        if group is not None and rule.ours not in REPEAT_CHILD_FIELD_TYPES:
            self.note(
                R.DROPPED,
                Reason.NOT_IN_GROUP,
                key=key,
                label=label,
                detail={"componentType": of_type},
            )
            return

        spec: Dict[str, Any] = {"title": title, "type": rule.ours}
        multiple = comp.get("multiple") is True
        choices: Dict[str, str] = {}
        if of_type in CHOICE_TYPES:
            found = self._choices(comp, of_type, key, label)
            if found is None:
                return
            choices, texts = found
            spec["choices"] = texts
            if of_type == "selectboxes" or (of_type == "select" and multiple):
                spec["type"] = "multiple_choice"
                spec["allowMultiple"] = True
            multiple = False
        elif multiple and of_type not in ("file",):
            self.note(R.CHANGED, Reason.MULTIPLE, key=key, label=label)

        validate = _dict(comp.get("validate"))
        required = validate.get("required") is True
        if rule.ours != "text":
            spec["required"] = required
        if of_type == "checkbox" and required:
            self.note(R.CHANGED, Reason.CHECKBOX_REQUIRED, key=key, label=label)

        description = label_text(comp.get("description"), limits.MAX_HELP)
        tooltip = label_text(comp.get("tooltip"), limits.MAX_HELP)
        if description:
            spec["description"] = description
            if tooltip and tooltip != description:
                self.note(R.DROPPED, Reason.SECOND_TEXT, R.INFO, key=key, label=label)
        elif tooltip:
            spec["description"] = tooltip
        placeholder = label_text(comp.get("placeholder"), 200) or rule.placeholder
        if placeholder and spec["type"] in (
            "short_text", "long_text", "email", "number", "phone_number"
        ):
            spec["placeholder"] = placeholder
        if col_span:
            spec["colSpan"] = col_span

        question = self._make(key, of_type, rule, label or title, page, group, spec)
        question.chain = list(chain)
        question.choices = choices
        question.multiple = comp.get("multiple") is True
        question.default_value = comp.get("defaultValue") not in (None, "")
        question.conditional = bool(chain) or self._hideable_parents > 0 or self._step_hideable
        question.rewritten = (
            bool(_dict(comp.get("prefill")).get("plugin"))
            or any(comp.get(name) for name in SCRIPT_KEYS)
            or bool(_list(comp.get("logic")))
        )

        if rule.converted and of_type != "checkbox":
            self.note(
                R.CHANGED, rule.converted, R.INFO, key=key, label=label,
                detail={"componentType": of_type},
            )
        elif rule.converted:
            self.note(R.CHANGED, rule.converted, R.INFO, key=key, label=label)
        self._flag_national_id(comp, question, key, label)
        self._carry_validation(comp, question, validate, of_type, key, label)
        self._noted_extras(comp, of_type, key, label)
        self._date_rules(comp, question, of_type, key, label)
        self._place(question, page, group)

        if of_type == "datetime":
            half = self._make(
                None, "time", TYPE_RULES["time"], f"{title} (time)", page, group,
                {"title": f"{title} (time)", "type": "short_text",
                 "placeholder": "HH:MM", "required": required},
            )
            half.chain = list(chain)
            half.validation["pattern"] = TIME_PATTERN
            if col_span:
                half.spec["colSpan"] = col_span
            self._place(half, page, group)
            self.note(R.CHANGED, Reason.DATETIME_SPLIT, R.INFO, key=key, label=label)

    # -- an address

    def _address_key(self, key: Optional[str], part: str) -> str:
        """The key of one of an address's questions: the component's key and
        the format's name for the part, made unique (two components may share
        a key in a careless export). It is only ever a name for reports: a
        condition names the component or a path inside it, never one of
        these, so it is not looked up."""
        base = f"{key or 'address'}.{part}"
        number = self._address_counts.get(base, 0)
        while True:
            number += 1
            found = base if number == 1 else f"{base}~{number}"
            if found not in self._address_keys and found not in self.seen_keys:
                break
        self._address_counts[base] = number
        self._address_keys.add(found)
        return found

    def _address_pattern(
        self, comp: Dict[str, Any], part: str, default: Optional[str], key, label
    ) -> Optional[str]:
        """The answer pattern of the postcode or the place: the one the
        component sets for it when it is one we can run, else the default."""
        config = _dict(_dict(_dict(comp.get("openForms")).get("components")).get(part))
        pattern = _dict(config.get("validate")).get("pattern")
        if not isinstance(pattern, str) or not pattern.strip():
            return default
        try:
            cleaned = checked_pattern(anchored(pattern))
        except ValueError:
            cleaned = None
        if cleaned and compile_pattern(cleaned) is not None:
            return cleaned
        self.note(
            R.DROPPED, Reason.VALIDATION, R.WARNING, key=key, label=label,
            detail={"property": "pattern"},
        )
        return default

    def _address(self, comp, page, chain, group, key, label, col_span) -> None:
        """An address component becomes five text questions in its place:
        street, house number, addition, postcode and place. The lookup that
        fills street and place from postcode and house number needs an
        address lookup service and is not carried, so all five are typed."""
        # refuse before planning what the form's size limit would refuse
        # after: an archive of nothing but addresses must not be planned in
        # full first (the same refusal as the check in ``_build_draft``)
        if self._planned + len(ADDRESS_PARTS) > _field_cap():
            raise refuse(
                "archive_too_complex",
                "The form has more pages or questions than a form can hold.",
                HTTPStatus.UNPROCESSABLE_ENTITY,
            )
        self._units += 1
        language = _component_language(comp) or self.language
        column = 2 if language == "nl" else 1
        base = (label or ADDRESS_FALLBACK_LABEL[language])[: limits.MAX_TITLE - 40]
        validate = _dict(comp.get("validate"))
        required = validate.get("required") is True
        derived = comp.get("deriveAddress") is True
        description = label_text(comp.get("description"), limits.MAX_HELP)
        tooltip = label_text(comp.get("tooltip"), limits.MAX_HELP)
        if description:
            if tooltip and tooltip != description:
                self.note(R.DROPPED, Reason.SECOND_TEXT, R.INFO, key=key, label=label)
        else:
            description = tooltip
        patterns = {
            "houseNumber": HOUSE_NUMBER_PATTERN,
            "houseNumberAddition": ADDITION_PATTERN,
            "postcode": self._address_pattern(
                comp, "postcode", POSTCODE_PATTERN, key, label
            ),
            "city": self._address_pattern(comp, "city", None, key, label),
        }
        for number, part in enumerate(ADDRESS_PARTS):
            budget.check()
            name = part[0]
            title = f"{base} \u2013 {part[column]}"
            # the source asks for street and place only when it looks them up
            # (then they are shown, read-only, and as required as the rest)
            needed = required and (name not in ADDRESS_DERIVED_PARTS or derived)
            spec: Dict[str, Any] = {
                "title": title,
                "type": "short_text",
                "required": needed and name != "houseNumberAddition",
            }
            if number == 0 and description:
                spec["description"] = description
            if col_span:
                spec["colSpan"] = col_span
            question = self._make(
                self._address_key(key, name), ADDRESS_TYPE, TYPE_RULES["textfield"],
                title, page, group, spec, register=False,
            )
            question.chain = list(chain)
            question.origin_key, question.origin_label = key, label
            question.unit = self._units
            if patterns.get(name):
                question.validation["pattern"] = patterns[name]
            if name == "houseNumberAddition":
                question.validation["maxLength"] = ADDITION_MAX_LENGTH
            self._place(question, page, group)
        self.note(
            R.CHANGED, Reason.CONVERTED_TO_TEXT,
            R.WARNING if derived else R.INFO, key=key, label=label,
            detail={
                "componentType": ADDRESS_TYPE,
                "questions": len(ADDRESS_PARTS),
                "lookup": "not_carried",
            },
        )
        if _list(validate.get("plugins")):
            self.note(
                R.DROPPED, Reason.VALIDATION, R.WARNING, key=key, label=label,
                detail={"property": "plugins"},
            )
        if _has_default(comp.get("defaultValue")):
            self.note(R.DROPPED, Reason.DEFAULT_VALUE, R.INFO, key=key, label=label)
        self._noted_extras(comp, ADDRESS_TYPE, key, label)

    def _place(self, question: Question, page: Page, group: Optional[Question]) -> None:
        if group is not None:
            group.children.append(question)
        else:
            page.items.append(question)
        self._planned += 1

    def _flag_national_id(self, comp, question: Question, key, label) -> None:
        rule = question.rule
        prefill = str(_dict(comp.get("prefill")).get("attribute") or "").lower()
        looks_like = (
            question.spec["type"] in ID_NUMBER_CANDIDATE_TYPES
            and bool(ID_NUMBER_TITLE.search(label or ""))
        )
        if rule.national_id or looks_like or any(p in prefill for p in _NATIONAL_ID_PREFILL):
            self.note(
                R.FLAGGED,
                Reason.NATIONAL_ID,
                key=key,
                label=label,
                flag=R.FLAG_NATIONAL_ID,
            )

    def _carry_validation(self, comp, question, validate, of_type, key, label) -> None:
        patch = question.validation
        ours = question.spec["type"]

        def dropped(prop: str, severity: str = R.INFO) -> None:
            self.note(
                R.DROPPED, Reason.VALIDATION, severity, key=key, label=label,
                detail={"property": prop},
            )

        pattern = validate.get("pattern")
        if rule_pattern := question.rule.pattern:
            patch["pattern"] = rule_pattern
        if isinstance(pattern, str) and pattern.strip() and of_type not in ("bsn", "iban", "time", "postcode"):
            if ours == "short_text":
                try:
                    cleaned = checked_pattern(anchored(pattern))
                except ValueError:
                    cleaned = None
                if cleaned and compile_pattern(cleaned) is not None:
                    patch["pattern"] = cleaned
                else:
                    dropped("pattern", R.WARNING)
            else:
                dropped("pattern")
        maximum = _int(validate.get("maxLength"))
        if maximum is not None and maximum > 0:
            if ours in ("short_text", "long_text"):
                patch["maxLength"] = maximum
            elif of_type == "email":
                dropped("maxLength")
        if _list(validate.get("plugins")):
            dropped("plugins", R.WARNING)
        if of_type in ("number", "currency"):
            low, high = _number(validate.get("min")), _number(validate.get("max"))
            if low is None and comp.get("allowNegative") is False:
                low = 0.0
            if low is not None and high is not None and low > high:
                dropped("min", R.WARNING)
                low = high = None
            if low is not None:
                patch["minValue"] = as_plain(low)
            if high is not None:
                patch["maxValue"] = as_plain(high)
        if of_type == "selectboxes":
            total = len(question.choices)
            low, high = _int(validate.get("minSelectedCount")), _int(
                validate.get("maxSelectedCount")
            )
            if low and 0 < low <= total:
                patch["minChoices"] = low
            if high and 0 < high <= total:
                patch["maxChoices"] = high
            if "minChoices" in patch and "maxChoices" in patch and patch["minChoices"] > patch["maxChoices"]:
                patch.pop("minChoices")
        if of_type == "time" and (validate.get("minTime") or validate.get("maxTime")):
            dropped("minTime")
        if _has_default(comp.get("defaultValue")):
            self.note(R.DROPPED, Reason.DEFAULT_VALUE, R.INFO, key=key, label=label)

    def _noted_extras(self, comp, of_type, key, label) -> None:
        if _dict(comp.get("prefill")).get("plugin"):
            self.note(
                R.DROPPED, Reason.PREFILL, key=key, label=label,
                detail={"plugin": str(_dict(comp.get("prefill")).get("plugin"))},
            )
        if _dict(comp.get("registration")).get("attribute"):
            self.note(
                R.DROPPED, Reason.REGISTRATION_ATTRIBUTE, R.INFO, once=True, step=None,
                kind=R.FEATURE,
            )
        if comp.get("disabled") is True:
            self.note(R.DROPPED, Reason.DISABLED, R.INFO, key=key, label=label)
        if _dict(comp.get("translatedErrors")) and any(
            _dict(v) for v in _dict(comp.get("translatedErrors")).values()
        ):
            self.note(
                R.DROPPED, Reason.ERROR_MESSAGES, R.INFO, once=True, step=None,
                kind=R.FEATURE,
            )
        if of_type == "file":
            restricted = (
                _list(_dict(comp.get("file")).get("type"))
                or comp.get("filePattern") not in (None, "", "*")
                or comp.get("maxNumberOfFiles") not in (None, "", 0)
                or comp.get("fileMaxSize") not in (None, "")
                or comp.get("multiple") is True
            )
            if restricted:
                self.note(
                    R.DROPPED, Reason.FILE_RESTRICTIONS, R.INFO, key=key, label=label
                )

    def _date_rules(self, comp, question, of_type, key, label) -> None:
        if of_type not in ("date", "datetime"):
            return
        forms = _dict(comp.get("openForms"))
        picker = _dict(comp.get("datePicker"))
        rules: List[Dict[str, Any]] = []

        def unsupported() -> None:
            self.note(R.DROPPED, Reason.DATE_RULE, R.INFO, key=key, label=label)

        for side, comparison_fixed, today_mode, today_cmp in (
            ("minDate", "on_or_after", "future", ("after", "on_or_after")),
            ("maxDate", "on_or_before", "past", ("before", "on_or_before")),
        ):
            config = _dict(forms.get(side))
            mode = config.get("mode")
            if mode in (None, ""):
                continue
            if mode == "fixedValue":
                raw = picker.get(side)
                day = raw[:10] if isinstance(raw, str) else ""
                if is_iso_date(day):
                    rules.append(
                        {"comparison": comparison_fixed, "target": "date", "date": day}
                    )
                else:
                    unsupported()
            elif mode == today_mode and not _dict(config.get("delta")).get("days") and not any(
                _dict(config.get("delta")).get(k) for k in ("years", "months", "days")
            ):
                include = config.get("includeToday") is True
                rules.append(
                    {
                        "comparison": today_cmp[1] if include else today_cmp[0],
                        "target": "today",
                    }
                )
            else:
                unsupported()
        question.date_rules = rules


# -------------------------------------------------------------- the build


def _retention(archive: Archive, report: Report) -> Tuple[Optional[str], Optional[str]]:
    """``(type, value)`` of the form's own retention, from the days it states
    for completed submissions."""
    options = _dict(archive.form.get("submissions_removal_options"))
    days = _int(options.get("successful_submissions_removal_limit"))
    method = options.get("successful_submissions_removal_method")
    if days is None:
        report.add(
            R.NOTED, R.SETTING, Reason.RETENTION_GLOBAL, R.INFO,
            key="submissions_removal_options", once=True,
        )
        result: Tuple[Optional[str], Optional[str]] = (None, None)
    elif 1 <= days <= MAX_RETENTION_DAYS:
        result = (ResponseRetentionType.DAYS.value, str(days))
        if method == "make_anonymous":
            report.add(
                R.DROPPED, R.SETTING, Reason.RETENTION_METHOD, R.WARNING,
                key="successful_submissions_removal_method", once=True,
            )
    else:
        report.add(
            R.NOTED, R.SETTING, Reason.RETENTION_GLOBAL, R.INFO,
            key="submissions_removal_options", once=True,
        )
        result = (None, None)
    others = [
        k for k in (
            "incomplete_submissions_removal_limit",
            "errored_submissions_removal_limit",
            "all_submissions_removal_limit",
        )
        if options.get(k) is not None
    ]
    if others:
        report.add(
            R.DROPPED, R.SETTING, Reason.RETENTION_OTHER, R.INFO,
            key="submissions_removal_options", once=True,
        )
    return result


def _plugin_names(items: Any, key: str) -> List[str]:
    names = []
    for item in _list(items)[:20]:
        value = _dict(item).get(key)
        if isinstance(value, str) and value:
            names.append(label_text(value, 60))
    return names


def _form_features(
    archive: Archive, report: Report, variables: Optional[Dict[str, V.Info]] = None
) -> None:
    """Everything form-wide that is not carried over."""
    form = archive.form

    def feature(reason: str, severity: str = R.WARNING, **kw) -> None:
        report.add(R.DROPPED, R.FEATURE, reason, severity, **kw)

    for plugin in _plugin_names(form.get("auth_backends"), "backend"):
        feature(Reason.SIGN_IN, key=plugin, detail={"plugin": plugin})
    if form.get("login_required") is True and not _list(form.get("auth_backends")):
        feature(Reason.SIGN_IN, key="login_required", once=True)
    if form.get("payment_backend"):
        plugin = label_text(form.get("payment_backend"), 60)
        feature(Reason.PAYMENT, key=plugin, detail={"plugin": plugin})
    # 4.0 writes the kind of form as ``type``; 3.x wrote a flag in the
    # appointment options
    if form.get("type") == "appointment" or (
        archive.is_3x and _dict(form.get("appointment_options")).get("is_appointment") is True
    ):
        feature(Reason.APPOINTMENT, key="appointment")
    for plugin in _plugin_names(form.get("registration_backends"), "backend"):
        feature(Reason.REGISTRATION, key=plugin, detail={"plugin": plugin})
    if form.get("translation_enabled") is True or any(
        _dict(v) for v in _dict(form.get("translations")).values()
    ):
        feature(Reason.TRANSLATIONS, R.INFO, key="translations", once=True)
    if any(
        form.get(k)
        for k in (
            "introduction_page_content",
            "explanation_template",
            "submission_confirmation_template",
        )
    ) or any(form.get(k) for k in ("theme", "category", "product")) or _help_set(form):
        feature(Reason.PRESENTATION, R.INFO, key="presentation", once=True)
    if form.get("ask_statement_of_truth") in ("required", "global_setting"):
        feature(
            Reason.STATEMENT_OF_TRUTH,
            R.WARNING if form.get("ask_statement_of_truth") == "required" else R.INFO,
            key="ask_statement_of_truth",
            once=True,
        )
    if any(form.get(k) for k in ("activate_on", "deactivate_on", "submission_limit")) or form.get(
        "maintenance_mode"
    ):
        feature(Reason.SCHEDULE, R.INFO, key="schedule", once=True)
    report.add(
        R.NOTED, R.SETTING, Reason.PRIVACY_POLICY, R.INFO,
        key="privacy_policy_url", once=True,
    )
    report.add(R.NOTED, R.SETTING, Reason.PURPOSE, R.INFO, key="purpose", once=True)
    for variable in archive.variables:
        if variable.get("source") not in (None, "user_defined"):
            continue
        name = variable.get("key")
        if isinstance(name, str) and name:
            data_type = variable.get("data_type") if isinstance(variable.get("data_type"), str) else ""
            info = (variables or {}).get(name)
            if info is not None and info.converted:
                report.add(
                    R.CHANGED, R.VARIABLE, Reason.USER_VARIABLE_CALCULATED, R.INFO,
                    key=name, label=variable.get("name"),
                    detail={"dataType": data_type},
                )
                continue
            detail: Dict[str, Any] = {"dataType": data_type}
            if info is not None and info.cause:
                detail["cause"] = info.cause
                detail.update(info.detail)
            report.add(
                R.DROPPED, R.VARIABLE, Reason.USER_VARIABLE, R.INFO,
                key=name, label=variable.get("name"), detail=detail,
            )
    for name in archive.ignored[:20]:
        report.add(
            R.IGNORED, R.ARCHIVE, Reason.ENTRY_IGNORED, R.INFO, key=name
        )


def _blank_form(title: str) -> StandardForm:
    """What the operations start from: title, welcome page, one ending and
    the new-form theme (as the other builders of forms in memory do)."""
    return StandardForm(
        title=title,
        builder_version="v2",
        theme=new_form_theme(),
        welcome_page=WelcomePageField(
            title=title, layout=LayoutType.SINGLE_COLUMN_NO_BACKGROUND
        ),
        thankyou_page=[ThankYouPageField(layout=LayoutType.SINGLE_COLUMN_NO_BACKGROUND)],
        fields=[],
    )


def _ref(name: str) -> str:
    return f"$ref:{name}"


class _Ops:
    """The operations of the build, each with what it is for, so a refusal
    can be reported against the right question."""

    def __init__(self) -> None:
        self.ops: List[Dict[str, Any]] = []
        self.meta: List[Tuple[str, Optional[Question], str]] = []

    def add(self, op: Dict[str, Any], kind: str, question: Optional[Question] = None, extra: str = "") -> None:
        self.ops.append(op)
        self.meta.append((kind, question, extra))


def _logic_ops(planner: Planner, ops: _Ops, report: Report) -> None:
    for question in _all_questions(planner):
        budget.check()
        if question.failed:
            continue
        own = question.chain
        rule, conflict = combine(own)
        name, title = _named(question)
        if conflict and _first(planner, question, "conflict"):
            planner.note(
                R.DROPPED, Reason.CONFLICT, kind=R.LOGIC, key=name,
                label=title, step=question.page,
            )
        if rule is None:
            continue
        conditions = []
        broken: Optional[str] = None
        for cond in rule.conds:
            source = planner.by_key.get(cond.source)
            if source is None or source.is_group or source.failed:
                broken = Reason.SOURCE_MISSING
                break
            if source.order >= question.order:
                broken = Reason.SOURCE_LATER
                break
            if source.group is not None and source.group is not question.group:
                broken = Reason.SOURCE_MISSING
                break
            try:
                comparison, value = translate(cond, source)
            except Unsupported as why:
                broken = why.reason
                break
            entry: Dict[str, Any] = {
                "fieldId": _ref(source.ref),
                "comparison": comparison,
            }
            if comparison not in ("IS_EMPTY", "IS_NOT_EMPTY"):
                entry["value"] = value
            conditions.append(entry)
        if broken:
            if _first(planner, question, ("broken", broken)):
                planner.note(
                    R.DROPPED, broken, kind=R.LOGIC, key=name or cond.source,
                    label=title, step=question.page,
                    detail={"source": cond.source},
                )
            continue
        ops.add(
            {
                "op": "set_field_logic",
                "fieldId": _ref(question.ref),
                "logic": {
                    "action": rule.action,
                    "operator": rule.operator,
                    "conditions": conditions,
                },
            },
            "logic",
            question,
        )


def _named(question: Question) -> Tuple[Optional[str], str]:
    """What a report calls a question: its own key and label, or, for one of
    several made from a component, that component's (they are not in the
    source file)."""
    if question.unit is not None:
        return question.origin_key, question.origin_label or ""
    return question.key, question.label


def _first(planner: Planner, question: Question, what: str) -> bool:
    """Whether this is the first report of ``what`` about the component the
    question was made from (always true for a question of its own): its
    questions share one outcome, so it is written once."""
    if question.unit is None:
        return True
    marker = (question.unit, what)
    if marker in planner._reported:
        return False
    planner._reported.add(marker)
    return True


def _all_questions(planner: Planner) -> List[Question]:
    out: List[Question] = []
    for page in planner.pages:
        for item in page.items:
            out.append(item)
            out.extend(item.children)
    return out


def _spec_of(question: Question) -> Dict[str, Any]:
    spec = dict(question.spec)
    return spec


def _build_ops(planner: Planner) -> _Ops:
    ops = _Ops()
    for number, page in enumerate(planner.pages):
        pref = f"p{number + 1}"
        ops.add({"op": "add_page", "ref": pref}, "page", None, pref)
        if page.title:
            ops.add(
                {"op": "set_section_title", "pageId": _ref(pref), "title": page.title},
                "title",
            )
        for item in page.items:
            if item.is_group:
                spec = dict(item.group_spec)
                ops.add(
                    {
                        "op": "add_group",
                        "pageId": _ref(pref),
                        "ref": item.ref,
                        **spec,
                        "fields": [_spec_of(c) for c in item.children],
                    },
                    "group",
                    item,
                )
            else:
                ops.add(
                    {"op": "add_field", "pageId": _ref(pref), "field": _spec_of(item)},
                    "field",
                    item,
                )
    for question in _all_questions(planner):
        if question.validation:
            ops.add(
                {
                    "op": "set_field_validation",
                    "fieldId": _ref(question.ref),
                    "validation": dict(question.validation),
                },
                "validation",
                question,
            )
        if question.date_rules:
            ops.add(
                {
                    "op": "update_field",
                    "fieldId": _ref(question.ref),
                    "patch": {"dateRules": question.date_rules},
                },
                "date_rules",
                question,
            )
    _logic_ops(planner, ops, planner.report)
    return ops


def _apply(planner: Planner, ops: _Ops, form: StandardForm) -> StandardForm:
    """Apply the operations; report what the form's own rules refused. Each
    operation is parsed alone, so one bad one cannot take the rest down."""
    parsed = []
    positions: List[int] = []
    for index, op in enumerate(ops.ops):
        budget.check()
        try:
            parsed.append(FormOps.model_validate({"ops": [op]}).ops[0])
            positions.append(index)
        except ValidationError:
            _refused(planner, ops, index, "invalid")
    # ``check_size=False``: the per-operation size count walks the whole form
    # for every operation; the build is bounded above (build_draft refuses a
    # form over MAX_PAGES / MAX_FIELDS before any operation runs) and the result
    # is validated as a whole at the end.
    # the deadline is checked after every operation: the engine's cost grows
    # with the form, so a big hostile one must not run it to the end
    form, results = apply_form_ops(
        form, parsed, on_step=lambda *_: budget.check(), check_size=False,
        check_calculations=False,
    )
    for result, index in zip(results, positions):
        kind, question, extra = ops.meta[index]
        if result.ok:
            if kind == "field" and question is not None:
                question.field_id = result.created_id
            elif kind == "page":
                planner.page_ids[extra] = result.created_id or ""
            continue
        if kind in ("field", "group", "page"):
            if question is not None:
                _mark_failed(question)
            if kind == "page":
                continue
        _refused(planner, ops, index, result.message)
    return form


def _calculations(planner: Planner, form: StandardForm) -> StandardForm:
    """The variables that qualify (``variables``) become calculated
    questions, placed after the last question each reads. They are added in
    a batch of their own, with the engine's check that calculations stay
    valid on: the first batch makes none, and that check costs a walk of the
    form per operation."""
    infos = planner.variables
    if any(info.carried for info in infos.values()):
        form = _add_calculations(planner, form)
    # a rule that only set a variable we did not carry after all is reported
    # like any other rule
    for index in planner.deferred:
        actions = [_dict(a) for a in _list(planner.rules[index].get("actions"))]
        if not all(
            infos[_dict(a).get("variable")].converted for a in actions
        ):
            planner.read_rule(index)
    return form


def _add_calculations(planner: Planner, form: StandardForm) -> StandardForm:
    position: Dict[int, int] = {}
    for number, page in enumerate(planner.pages):
        for item in page.items:
            position[id(item)] = number
    sources: Dict[str, V.Source] = {}
    unusable: Dict[str, str] = {}
    for key, question in planner.by_key.items():
        if question.failed:
            unusable[key] = V.Cause.SOURCE_MISSING
        elif question.is_group or question.of_type not in ("number", "currency"):
            unusable[key] = V.Cause.SOURCE_NOT_NUMBER
        elif question.group is not None:
            unusable[key] = V.Cause.SOURCE_IN_GROUP
        elif question.multiple:
            unusable[key] = V.Cause.SOURCE_MULTIPLE
        elif question.rewritten:
            unusable[key] = V.Cause.SOURCE_REWRITTEN
        elif question.default_value:
            unusable[key] = V.Cause.SOURCE_DEFAULT
        elif question.conditional:
            unusable[key] = V.Cause.SOURCE_CONDITIONAL
        elif question.field_id is None:
            unusable[key] = V.Cause.SOURCE_MISSING
        else:
            sources[key] = V.Source(
                question.field_id, (position.get(id(question), 0), question.order)
            )
    ordered = V.resolve(planner.variables, sources, unusable, planner.seen_keys, planner.written)

    questions = _all_questions(planner)
    room = _field_cap() - (len(questions) + sum(1 for q in questions if q.is_group))
    keep = ordered[: max(0, min(room, V.MAX_CALCULATIONS))]
    for info in ordered[len(keep):]:
        info.fail(V.Cause.TOO_MANY)
    if not keep:
        return form

    last_page = len(planner.pages) - 1
    ids: Dict[str, str] = {key: source.id for key, source in sources.items()}
    where: Dict[str, Tuple[int, int, int]] = {
        key: (*source.pos, 0) for key, source in sources.items()
    }
    after_last: Dict[str, str] = {}
    ops: List[Dict[str, Any]] = []
    made: List[V.Info] = []
    for number, info in enumerate(keep, start=1):
        budget.check()
        ref = f"c{number}"
        best: Optional[Tuple[int, int, int]] = None
        target: Optional[str] = None
        for name in info.refs:
            if best is None or where[name] > best:
                best, target = where[name], ids[name]
        if best is None:
            best = (last_page, 10**9, 0)
        page_ref = f"p{best[0] + 1}"
        after = after_last.get(target or "", target)
        if target is not None:
            after_last[target] = _ref(ref)
        ids[info.key] = _ref(ref)
        where[info.key] = (best[0], best[1], number)
        title = label_text(info.name, limits.MAX_TITLE) or label_text(info.key, limits.MAX_TITLE)
        op: Dict[str, Any] = {
            "op": "add_field",
            "pageId": planner.page_ids.get(page_ref, ""),
            "field": {
                "title": title or "Calculation",
                "type": "calculated",
                "expression": V.to_ast(info.tree, ids),
                "format": {"style": "number"},
                "hiddenFromRespondents": True,
                "unansweredAsZero": False,
                "ref": ref,
            },
        }
        if after is not None:
            op["afterFieldId"] = after
        ops.append(op)
        made.append(info)
    parsed: List[Any] = []
    owners: List[V.Info] = []
    for op, info in zip(ops, made):
        try:
            parsed.append(FormOps.model_validate({"ops": [op]}).ops[0])
            owners.append(info)
        except ValidationError:
            info.fail(V.Cause.REJECTED)
    form, results = apply_form_ops(
        form, parsed, on_step=lambda *_: budget.check(), check_size=False,
        check_calculations=True,
    )
    for result, info in zip(results, owners):
        if result.ok:
            info.converted = True
        else:
            info.fail(V.Cause.REJECTED)
    return form


def _mark_failed(question: Question) -> None:
    question.failed = True
    for child in question.children:
        child.failed = True


def _refused(planner: Planner, ops: _Ops, index: int, why: str) -> None:
    kind, question, _ = ops.meta[index]
    if question is None:
        return
    if question.failed and kind not in ("field", "group"):
        return  # it hangs on a question that was refused; that one is reported
    name, title = _named(question)
    if kind in ("field", "group"):
        _mark_failed(question)
        if _first(planner, question, "rejected"):
            planner.note(
                R.DROPPED, Reason.REJECTED, key=name, label=title,
                step=question.page,
            )
    elif kind == "validation":
        if _first(planner, question, "validation"):
            planner.note(
                R.DROPPED, Reason.VALIDATION, R.INFO, key=name,
                label=title, step=question.page, detail={"property": "rule"},
            )
    elif kind == "date_rules":
        planner.note(
            R.DROPPED, Reason.DATE_RULE, R.INFO, key=name,
            label=title, step=question.page,
        )
    elif kind == "logic":
        if _first(planner, question, "logic_rejected"):
            planner.note(
                R.DROPPED, Reason.REJECTED, kind=R.LOGIC, key=name,
                label=title, step=question.page,
            )


def build_draft(archive: Archive) -> Built:
    """The draft form and the report, or ``ImportRefused``. Within the
    import's work budget; anything unexpected from the file's content is a
    refusal of the archive, not a server error."""
    with budget.scope():
        try:
            return _build_draft(archive)
        except ImportRefused:
            raise
        except Exception as error:  # noqa: BLE001
            raise unexpected(error) from None


def _build_draft(archive: Archive) -> Built:
    report = Report()
    planner = Planner(archive, report)
    planner.plan()

    questions = _all_questions(planner)
    if not planner.pages or not any(q.spec.get("type") != "text" for q in questions):
        raise refuse(
            "no_importable_fields",
            "Nothing in the archive can be imported as a question.",
            HTTPStatus.UNPROCESSABLE_ENTITY,
            reportItems=report.items[:50],
        )
    if len(planner.pages) > MAX_PAGES or (
        len(questions) + sum(1 for q in questions if q.is_group)
        > _field_cap()
    ):
        raise refuse(
            "archive_too_complex",
            "The form has more pages or questions than a form can hold.",
            HTTPStatus.UNPROCESSABLE_ENTITY,
        )

    title = label_text(archive.form.get("name"), limits.MAX_TITLE) or "Imported form"
    form = _blank_form(title)
    ops = _build_ops(planner)
    form = _apply(planner, ops, form)
    form = _calculations(planner, form)

    _form_features(archive, report, planner.variables)
    retention_type, retention_value = _retention(archive, report)
    form.settings = StandardFormSettings(
        privacy_policy_url="",
        response_expiration=retention_value or "",
        response_expiration_type=(
            ResponseRetentionType(retention_type) if retention_type else None
        ),
        response_data_owner_field="",
    )

    created = [q for q in _all_questions(planner) if not q.failed]
    summary = {
        "pages": len(planner.pages),
        "fields": sum(
            1 for q in created if not q.is_group and q.spec.get("type") != "text"
        ),
        "logicRules": sum(1 for kind, q, _ in ops.meta if kind == "logic" and q and not q.failed),
        "repeatingGroups": sum(1 for q in created if q.is_group),
        "dropped": report.dropped,
        "flagged": report.flagged,
    }
    calculations = sum(1 for info in planner.variables.values() if info.converted)
    if calculations:
        summary["calculations"] = calculations
    return Built(form=form, report=report, summary=summary, title=title)
