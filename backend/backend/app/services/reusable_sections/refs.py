"""References between the questions of a reusable section (pure).

A section fragment is ``(fields, containers)`` in the form spec's shape
(camelCase, ``pages[].fields`` / ``pages[].containers``). Everything here works
on those plain dicts and nothing reads a database.

One walk, three uses (``transform``):

* ``isolate``: keep what points at a question of the section, drop what points
  anywhere else (another question of the form the section came from, a hidden
  field), each with a warning. Run when a section is saved to the library, and
  again before every insert (stored data can be older than the rules).
* ``remap``: give every question a new id and rewrite every reference to it.
* ``assert_closed``: raise when any reference names something that is not a
  question of the fragment. Run on the result of a remap: whatever the stored
  section said, an inserted question never points at a question of another form.

What names a question id (see ``docs/reusable-sections.md``): logic conditions
(of a question, a choice, a container, a rule), option filters, the parent of a
list source, date rules that compare with a question, field rules (conditions
and expressions), a calculation's expression, answer pipes in rich titles and
``{{field:<id>}}`` tokens in plain strings, container members.

Everything is iterative (a document of any depth cannot exhaust the stack) and
never evaluates anything.
"""

import re
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterator, List, Optional, Tuple

PIPE_NODE = "answerPipe"
DATE_RANGE_PARTS = ("start", "end")
_TOKEN = re.compile(r"\{\{(field|hidden):([^|{}]*)((?:\|[^{}]*)?)\}\}")

# warning codes (the webapp has a sentence for each)
CONDITION_DROPPED = "condition_dropped"
OPTION_FILTER_DROPPED = "option_filter_dropped"
SOURCE_PARENT_DROPPED = "source_parent_dropped"
DATE_RULE_DROPPED = "date_rule_dropped"
RULE_DROPPED = "rule_dropped"
PIPE_DROPPED = "pipe_dropped"
CONTAINER_CONDITION_DROPPED = "container_condition_dropped"
CALCULATION_LEFT_OUT = "calculation_left_out"
FORM_ANSWERS_SOURCE_DROPPED = "form_answers_source_dropped"
LIST_SOURCE_DROPPED = "list_source_dropped"
SHARE_AS_CHOICES_DROPPED = "share_as_choices_dropped"


class EscapeError(Exception):
    """A reference names something outside the fragment (``assert_closed``)."""


@dataclass
class SectionWarning:
    code: str
    field_id: Optional[str] = None
    title: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        return {"code": self.code, "fieldId": self.field_id, "title": self.title}


def plain_title(field: Dict[str, Any]) -> str:
    """The question's title as text (a rich title's text nodes joined)."""
    title = field.get("title")
    if isinstance(title, str):
        return title.strip()[:200]
    parts: List[str] = []
    stack = [title] if isinstance(title, dict) else []
    while stack and len(parts) < 400:
        node = stack.pop()
        if isinstance(node, dict):
            if isinstance(node.get("text"), str):
                parts.append(node["text"])
            stack.extend(reversed(node.get("content") or []))
    return "".join(parts).strip()[:200]


# --------------------------------------------------------------------- walking


def questions(fields: List[Dict[str, Any]]) -> Iterator[Dict[str, Any]]:
    """Every question, group children included, in document order."""
    stack = list(reversed(fields or []))
    while stack:
        field = stack.pop()
        if not isinstance(field, dict):
            continue
        yield field
        stack.extend(reversed(field.get("fields") or []))


def question_ids(fields: List[Dict[str, Any]]) -> List[str]:
    return [str(f["id"]) for f in questions(fields) if f.get("id")]


def container_ids(containers: List[Dict[str, Any]]) -> List[str]:
    found: List[str] = []
    for container in containers or []:
        found.append(str(container.get("id")))
        found.extend(str(t.get("id")) for t in container.get("tabs") or [])
    return found


def expression_variables(ast: Any) -> List[str]:
    """The ``var`` keys of an expression (``{"var": key}`` nodes), iterative."""
    found: List[str] = []
    stack = [ast]
    while stack:
        node = stack.pop()
        if isinstance(node, dict) and len(node) == 1:
            op, value = next(iter(node.items()))
            if op == "var" and isinstance(value, str):
                found.append(value)
            elif isinstance(value, list):
                stack.extend(value)
    return found


# -------------------------------------------------------------------- mapping


class Mapper:
    """Maps the ids of a fragment. ``mapping`` holds the ids that stay in the
    fragment (identity for ``isolate``, old to new for ``remap``); an id that is
    not in it is "outside" (``None``). ``fresh_rule_id`` renames field rules."""

    def __init__(
        self,
        mapping: Dict[str, str],
        *,
        strict: bool = False,
        fresh_rule_id: Optional[Callable[[str], str]] = None,
    ):
        self.mapping = mapping
        self.strict = strict
        self.fresh_rule_id = fresh_rule_id
        self.warnings: List[SectionWarning] = []

    def id(self, value: Any) -> Optional[str]:
        return self.mapping.get(value) if isinstance(value, str) else None

    def key(self, value: Any) -> Optional[str]:
        """An expression or pipe key: ``<id>``, ``<id>.start|end``,
        ``<group>.<child>``. Hidden-field names are never in the mapping."""
        if not isinstance(value, str) or not value:
            return None
        whole = self.mapping.get(value)
        if whole is not None:
            return whole
        parts = value.split(".")
        if len(parts) < 2:
            return None
        mapped: List[str] = []
        for i, part in enumerate(parts):
            target = self.mapping.get(part)
            if target is None:
                if i == len(parts) - 1 and part in DATE_RANGE_PARTS:
                    mapped.append(part)
                    continue
                return None
            mapped.append(target)
        return ".".join(mapped)

    def dropped(self, code: str, field: Optional[Dict[str, Any]]) -> None:
        if self.strict:
            raise EscapeError(code)
        self.warnings.append(
            SectionWarning(
                code,
                str(field.get("id")) if field and field.get("id") else None,
                plain_title(field) if field else None,
            )
        )


# conditions -----------------------------------------------------------------


def _condition_maps(condition: Any, m: Mapper) -> bool:
    """Does every id the condition names stay in the fragment?"""
    if not isinstance(condition, dict) or m.id(condition.get("fieldId")) is None:
        return False
    child = condition.get("childFieldId")
    return not child or m.id(child) is not None


def _conditions(
    conditions: Optional[List[Dict[str, Any]]],
    m: Mapper,
    field: Optional[Dict[str, Any]],
    code: str,
) -> List[Dict[str, Any]]:
    kept: List[Dict[str, Any]] = []
    for condition in conditions or []:
        if not isinstance(condition, dict):
            continue
        field_id = m.id(condition.get("fieldId"))
        child = condition.get("childFieldId")
        child_id = m.id(child) if child else None
        if field_id is None or (child and child_id is None):
            m.dropped(code, field)
            continue
        condition["fieldId"] = field_id
        if child:
            condition["childFieldId"] = child_id
        kept.append(condition)
    return kept


def _logic(
    logic: Optional[Dict[str, Any]],
    m: Mapper,
    field: Optional[Dict[str, Any]],
    code: str = CONDITION_DROPPED,
) -> Optional[Dict[str, Any]]:
    if not isinstance(logic, dict):
        return None
    conditions = _conditions(logic.get("conditions"), m, field, code)
    if not conditions:
        return None
    logic["conditions"] = conditions
    return logic


# text, pipes and tokens -----------------------------------------------------


def _rewrite_tokens(text: str, m: Mapper, field: Dict[str, Any]) -> str:
    def swap(match: "re.Match[str]") -> str:
        kind, key, tail = match.group(1), match.group(2), match.group(3)
        if kind == "hidden":
            m.dropped(PIPE_DROPPED, field)
            return tail[1:]  # the fallback text stays
        mapped = m.key(key)
        if mapped is None:
            m.dropped(PIPE_DROPPED, field)
            return tail[1:]
        return "{{field:" + mapped + tail + "}}"

    return _TOKEN.sub(swap, text)


def _pipe_ok(node: Dict[str, Any], m: Mapper) -> Optional[Dict[str, Any]]:
    """The pipe node with its key rewritten, or None when it points outside."""
    attrs = node.get("attrs") or {}
    kind = attrs.get("kind")
    key = attrs.get("pipeKey")
    if kind == "hidden":
        return None
    if kind == "group":
        parts = str(key or "").split(":")
        group = m.id(parts[0])
        child = m.id(parts[2]) if len(parts) > 2 else None
        if group is None or (len(parts) > 2 and child is None):
            return None
        parts[0] = group
        if len(parts) > 2:
            parts[2] = child  # type: ignore[assignment]
        attrs["pipeKey"] = ":".join(parts)
        return node
    mapped = m.key(key)
    if mapped is None:
        return None
    attrs["pipeKey"] = mapped
    return node


def _walk_rich(doc: Any, m: Mapper, field: Dict[str, Any]) -> None:
    """Rewrite the pipes of a rich-text document in place, drop the ones that
    point outside, and rewrite tokens in text nodes."""
    stack = [doc] if isinstance(doc, dict) else []
    while stack:
        node = stack.pop()
        content = node.get("content")
        if isinstance(node.get("text"), str):
            node["text"] = _rewrite_tokens(node["text"], m, field)
        if not isinstance(content, list):
            continue
        kept = []
        for child in content:
            if isinstance(child, dict) and child.get("type") == PIPE_NODE:
                if _pipe_ok(child, m) is None:
                    m.dropped(PIPE_DROPPED, field)
                    continue
            kept.append(child)
        node["content"] = kept
        stack.extend(c for c in kept if isinstance(c, dict))


# expressions ----------------------------------------------------------------


def _expression(ast: Any, m: Mapper) -> bool:
    """Rewrite the ``var`` keys of ``ast`` in place; False (nothing is changed
    after the first outside key) when one points outside."""
    nodes: List[Dict[str, Any]] = []
    stack = [ast]
    while stack:
        node = stack.pop()
        if isinstance(node, dict) and len(node) == 1:
            op, value = next(iter(node.items()))
            if op == "var" and isinstance(value, str):
                if m.key(value) is None:
                    return False
                nodes.append(node)
            elif isinstance(value, list):
                stack.extend(value)
    for node in nodes:
        node["var"] = m.key(node["var"])
    return True


# a question ------------------------------------------------------------------


def _rules(field: Dict[str, Any], m: Mapper) -> Optional[List[Dict[str, Any]]]:
    kept: List[Dict[str, Any]] = []
    for rule in field.get("rules") or []:
        when = rule.get("when") or {}
        then = rule.get("then") or {}
        set_value = then.get("setValue") or {}
        ok = True
        if when.get("conditions") is not None:
            ok = all(_condition_maps(c, m) for c in when["conditions"])
            if ok:
                _conditions(when["conditions"], m, field, RULE_DROPPED)
        if ok and when.get("expression") is not None:
            ok = _expression(when["expression"], m)
        if ok and set_value.get("expression") is not None:
            ok = _expression(set_value["expression"], m)
        if not ok:
            # a rule is dropped whole (dropping one of its conditions would make
            # it fire more often)
            m.dropped(RULE_DROPPED, field)
            continue
        for key in ("title", "description"):
            if isinstance(then.get(key), str):
                then[key] = _rewrite_tokens(then[key], m, field)
        if m.fresh_rule_id is not None and rule.get("id"):
            rule["id"] = m.fresh_rule_id(str(rule["id"]))
        kept.append(rule)
    return kept or None


def _transform_field(field: Dict[str, Any], m: Mapper) -> bool:
    """Rewrite one question (its children are the caller's). False: leave this
    question out (a calculation that reads outside)."""
    if field.get("type") == "calculated" and field.get("expression") is not None:
        if not _expression(field["expression"], m):
            m.dropped(CALCULATION_LEFT_OUT, field)
            return False
    if isinstance(field.get("title"), dict):
        _walk_rich(field["title"], m, field)
    elif isinstance(field.get("title"), str) and "{{" in field["title"]:
        field["title"] = _rewrite_tokens(field["title"], m, field)
    new_id = m.id(field.get("id"))
    if new_id is None:
        # the question's own id is not in the mapping: nothing to rewrite
        return True
    field["id"] = new_id

    if field.get("logic") is not None:
        field["logic"] = _logic(field["logic"], m, field)
    for choice in field.get("choices") or []:
        if choice.get("logic") is not None:
            choice["logic"] = _logic(choice["logic"], m, field)

    option_filter = field.get("optionFilter")
    if isinstance(option_filter, dict):
        target = m.id(option_filter.get("fieldId"))
        if target is None:
            m.dropped(OPTION_FILTER_DROPPED, field)
            field["optionFilter"] = None
        else:
            option_filter["fieldId"] = target

    source = field.get("optionSource")
    if isinstance(source, dict):
        if source.get("kind") == "form_answers":
            m.dropped(FORM_ANSWERS_SOURCE_DROPPED, field)
            field["optionSource"] = None
        elif source.get("parentFieldId"):
            target = m.id(source["parentFieldId"])
            if target is None:
                m.dropped(SOURCE_PARENT_DROPPED, field)
                source.pop("parentFieldId", None)
            else:
                source["parentFieldId"] = target

    if field.get("shareAsChoices"):
        m.dropped(SHARE_AS_CHOICES_DROPPED, field)
        field["shareAsChoices"] = None

    date_rules = []
    for rule in field.get("dateRules") or []:
        if rule.get("target") == "field":
            target = m.id(rule.get("fieldId"))
            if target is None:
                m.dropped(DATE_RULE_DROPPED, field)
                continue
            rule["fieldId"] = target
        date_rules.append(rule)
    if field.get("dateRules") is not None:
        field["dateRules"] = date_rules or None

    if field.get("rules") is not None:
        field["rules"] = _rules(field, m)

    for key in ("description", "placeholder", "whyWeAsk", "label"):
        if isinstance(field.get(key), str) and "{{" in field[key]:
            field[key] = _rewrite_tokens(field[key], m, field)
    repeat = field.get("repeat")
    if isinstance(repeat, dict) and isinstance(repeat.get("itemTitle"), str):
        repeat["itemTitle"] = _rewrite_tokens(repeat["itemTitle"], m, field)
    return True


def _transform_fields(
    fields: List[Dict[str, Any]], m: Mapper
) -> List[Dict[str, Any]]:
    kept: List[Dict[str, Any]] = []
    for field in fields:
        if not isinstance(field, dict):
            continue
        if not _transform_field(field, m):
            continue
        if field.get("fields") is not None:
            field["fields"] = _transform_fields(field["fields"], m)
        kept.append(field)
    return kept


def _members(
    members: Optional[List[str]], ids: Callable[[str], Optional[str]], m: Mapper
) -> List[str]:
    kept: List[str] = []
    for member in members or []:
        target = ids(member)
        if target is None:
            if m.strict:
                raise EscapeError("member")
            continue
        kept.append(target)
    return kept


def _transform_containers(
    containers: List[Dict[str, Any]],
    m: Mapper,
    ids: Callable[[str], Optional[str]],
    layout_id: Optional[Callable[[str, str], str]],
) -> List[Dict[str, Any]]:
    kept: List[Dict[str, Any]] = []
    for container in containers or []:
        if container.get("logic") is not None:
            container["logic"] = _logic(
                container["logic"], m, None, CONTAINER_CONDITION_DROPPED
            )
        if layout_id is not None:
            container["id"] = layout_id("container", str(container["id"]))
        if container.get("type") == "tabs":
            tabs = []
            for tab in container.get("tabs") or []:
                tab["fields"] = _members(tab.get("fields"), ids, m)
                if layout_id is not None:
                    tab["id"] = layout_id("tab", str(tab["id"]))
                if tab["fields"]:
                    tabs.append(tab)
            if not tabs:
                continue
            container["tabs"] = tabs
        else:
            container["fields"] = _members(container.get("fields"), ids, m)
            if not container["fields"]:
                continue
        kept.append(container)
    return kept



def isolate(
    fields: List[Dict[str, Any]], containers: List[Dict[str, Any]]
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[SectionWarning]]:
    """Drop, **in place**, every reference that points outside the fragment
    (and what cannot stay without it), with a warning each. A calculation that
    reads outside is left out, so the walk repeats until nothing more goes."""
    warnings: List[SectionWarning] = []
    kept = fields
    while True:
        present = set(question_ids(kept))
        m = Mapper({x: x for x in present})
        kept = _transform_fields(kept, m)
        warnings.extend(m.warnings)
        if set(question_ids(kept)) == present:
            break
    present = set(question_ids(kept))
    m = Mapper({x: x for x in present})
    kept_containers = _transform_containers(
        containers, m, lambda x: x if x in present else None, None
    )
    warnings.extend(m.warnings)
    return kept, kept_containers, warnings


def remap(
    fields: List[Dict[str, Any]],
    containers: List[Dict[str, Any]],
    mapping: Dict[str, str],
    *,
    fresh_rule_id: Optional[Callable[[str], str]] = None,
    layout_id: Optional[Callable[[str, str], str]] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Rewrite **in place**: every question gets ``mapping[old id]`` and every
    reference follows; rule, container and tab ids are renamed by the given
    functions. Strict: a reference that names anything but a question of the
    fragment raises ``EscapeError`` (run ``isolate`` first)."""
    m = Mapper(mapping, strict=True, fresh_rule_id=fresh_rule_id)
    kept = _transform_fields(fields, m)
    kept_containers = _transform_containers(containers, m, mapping.get, layout_id)
    return kept, kept_containers


def assert_closed(fields: List[Dict[str, Any]], containers: List[Dict[str, Any]]) -> None:
    """Raise ``EscapeError`` unless every reference of the fragment names a
    question of the fragment. Changes nothing."""
    import copy

    present = set(question_ids(fields))
    m = Mapper({x: x for x in present}, strict=True)
    probe = copy.deepcopy(fields)
    _transform_fields(probe, m)
    _transform_containers(
        copy.deepcopy(containers), m, lambda x: x if x in present else None, None
    )
