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
from backend.app.services.open_formulieren.errors import refuse
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
    CHOICE_TYPES,
    GROUP_TYPES,
    LAYOUT_TYPES,
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


def _int(value: Any) -> Optional[int]:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value == int(value):
        return int(value)
    if isinstance(value, str) and value.strip().lstrip("-").isdigit():
        return int(value.strip())
    return None


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


def _dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _last_segment(url: Any) -> str:
    """The id at the end of a link to a resource of the source instance. The
    link is only ever read for that id: never fetched, never used as an
    address."""
    if not isinstance(url, str):
        return ""
    return urlsplit(url).path.rstrip("/").rsplit("/", 1)[-1]


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
        else a rule does is reported and ignored."""
        rules = sorted(
            self.archive.logic,
            key=lambda r: r.get("order") if isinstance(r.get("order"), int) else 0,
        )
        for index, rule in enumerate(rules):
            name = f"rule-{index + 1}"
            label = rule.get("description")
            try:
                trigger = parse_trigger(rule.get("json_logic_trigger"))
            except Unsupported as why:
                self.note(
                    R.DROPPED, why.reason, kind=R.LOGIC, key=name, label=label, step=None
                )
                continue
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
        if of_type not in TYPE_RULES and of_type not in LAYOUT_TYPES | GROUP_TYPES:
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

    # -- one question

    def _make(self, key, of_type, rule, label, page, group, spec) -> Question:
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
        if key and key not in self.by_key:
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
            if not text:
                continue
            base, number = text, 2
            while text in texts:
                text = f"{base} ({number})"
                number += 1
            if value in by_value:
                continue
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

    def _place(self, question: Question, page: Page, group: Optional[Question]) -> None:
        if group is not None:
            group.children.append(question)
        else:
            page.items.append(question)

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
                    cleaned = checked_pattern(pattern)
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
                patch["minValue"] = int(low) if low == int(low) else low
            if high is not None:
                patch["maxValue"] = int(high) if high == int(high) else high
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


def _form_features(archive: Archive, report: Report) -> None:
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
    if form.get("type") == "appointment":
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
    ) or any(form.get(k) for k in ("theme", "category", "product", "help_dialog")):
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
            report.add(
                R.DROPPED, R.VARIABLE, Reason.USER_VARIABLE, R.INFO,
                key=name, label=variable.get("name"),
                detail={"dataType": variable.get("data_type") if isinstance(variable.get("data_type"), str) else ""},
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
        if question.failed:
            continue
        own = question.chain
        rule, conflict = combine(own)
        if conflict:
            planner.note(
                R.DROPPED, Reason.CONFLICT, kind=R.LOGIC, key=question.key,
                label=question.label, step=question.page,
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
            planner.note(
                R.DROPPED, broken, kind=R.LOGIC, key=question.key or cond.source,
                label=question.label, step=question.page,
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
        ops.add({"op": "add_page", "ref": pref}, "page")
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
        try:
            parsed.append(FormOps.model_validate({"ops": [op]}).ops[0])
            positions.append(index)
        except ValidationError:
            _refused(planner, ops, index, "invalid")
    form, results = apply_form_ops(form, parsed)
    for result, index in zip(results, positions):
        if result.ok:
            continue
        kind, question, _ = ops.meta[index]
        if kind in ("field", "group", "page"):
            if question is not None:
                _mark_failed(question)
            if kind == "page":
                continue
        _refused(planner, ops, index, result.message)
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
    if kind in ("field", "group"):
        _mark_failed(question)
        planner.note(
            R.DROPPED, Reason.REJECTED, key=question.key, label=question.label,
            step=question.page,
        )
    elif kind == "validation":
        planner.note(
            R.DROPPED, Reason.VALIDATION, R.INFO, key=question.key,
            label=question.label, step=question.page, detail={"property": "rule"},
        )
    elif kind == "date_rules":
        planner.note(
            R.DROPPED, Reason.DATE_RULE, R.INFO, key=question.key,
            label=question.label, step=question.page,
        )
    elif kind == "logic":
        planner.note(
            R.DROPPED, Reason.REJECTED, kind=R.LOGIC, key=question.key,
            label=question.label, step=question.page,
        )


def build_draft(archive: Archive) -> Built:
    """The draft form and the report, or ``ImportRefused``."""
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
        len(questions) + sum(1 for q in questions if q.is_group) > MAX_FIELDS
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

    _form_features(archive, report)
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
    return Built(form=form, report=report, summary=summary, title=title)
