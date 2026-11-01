"""Layout containers of a page: structure checks, repair and membership.

A page's ``properties.containers`` (``standard_form.LayoutContainer``) groups
questions into a panel, a field set or a strip of tabs. It is layout only: the
page's flat question list stays what answers, logic, rules and exports read.
What holds the model together:

* members are top-level questions of the page (never a repeating group's
  children, never an internal "for office use" question), each in at most one
  container;
* the members of a container (tabs in strip order, then each tab's members)
  appear in the page in that order with no respondent-facing question between
  them, so the display order is the page order;
* container and tab ids are unique across the form and are never the id of a
  question, group child or page (the builder and the respondent page key
  state and DOM ids by them);
* a container's rule has at most ``CONTAINER_CONDITIONS_MAX`` conditions.

``repair_form`` makes a form that broke these (a question removed or moved by
a client that does not know containers) valid again; ``form_problems`` reports
what repair cannot (and what an explicit write must not contain). The webapp's
twin is ``webapp/src/utils/layout-containers.ts``; the shared cases are in
``docs/spec/layout-containers.cases.json``.
"""

from typing import Any, Dict, Iterable, List, Optional, Tuple

from common.models.standard_form import CONTAINER_CONDITIONS_MAX

# ``logic_sources`` (backend repeating_groups.py) returns a ``LogicSources``
# dict whose ``container_logic`` attribute maps a member's id to the logic of
# the containers it is in (``container_logic_index``): the dict's own keys stay
# the form's questions, so nothing that walks it changes.

CONTAINER_ID_PREFIX = "c"
TAB_ID_PREFIX = "t"


def _get(obj: Any, name: str) -> Any:
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def _type_text(field: Any) -> str:
    kind = _get(field, "type")
    return str(getattr(kind, "value", kind))


def page_fields(page: Any) -> List[Any]:
    props = _get(page, "properties")
    return list(_get(props, "fields") or [])


def page_containers(page: Any) -> List[Any]:
    props = _get(page, "properties")
    return list(_get(props, "containers") or [])


def respondent_ids(page: Any) -> List[str]:
    """Ids of the page's questions in order, internal ones left out (they are
    never shown to respondents, so they do not count for "next to each
    other")."""
    return [
        str(_get(field, "id"))
        for field in page_fields(page)
        if not _get(field, "internal")
    ]


def container_tabs(container: Any) -> List[Any]:
    """The tabs of a ``tabs`` container; for a panel or field set its one
    list of members is returned as a single pseudo tab."""
    if _get(container, "type") == "tabs":
        return list(_get(container, "tabs") or [])
    return [container]


def members_of(container: Any) -> List[str]:
    """A container's member ids in strip order (tabs one after the other)."""
    found: List[str] = []
    for tab in container_tabs(container):
        found.extend(str(x) for x in (_get(tab, "fields") or []))
    return found


def all_containers(form: Any) -> Iterable[Tuple[Any, Any]]:
    """``(page, container)`` for every container of every page."""
    for page in _get(form, "fields") or []:
        if _type_text(page) != "slide":
            continue
        for container in page_containers(page):
            yield page, container


def form_has_containers(form: Any) -> bool:
    return any(True for _ in all_containers(form))


def used_ids(form: Any) -> set:
    """Every container and tab id of the form."""
    ids = set()
    for _, container in all_containers(form):
        ids.add(str(_get(container, "id")))
        if _get(container, "type") == "tabs":
            for tab in _get(container, "tabs") or []:
                ids.add(str(_get(tab, "id")))
    return ids


def page_item_ids(page: Any) -> set:
    """The ids on one page: the page itself, its questions and a repeating
    group's children."""
    ids = {str(_get(page, "id"))}
    for field in page_fields(page):
        ids.add(str(_get(field, "id")))
        for child in _get(_get(field, "properties"), "fields") or []:
            ids.add(str(_get(child, "id")))
    return ids


def form_item_ids(form: Any) -> set:
    """Every page, question and group-child id of the form: what a container
    or tab id must not equal."""
    ids: set = set()
    for page in _get(form, "fields") or []:
        if _type_text(page) == "slide":
            ids |= page_item_ids(page)
    return ids


def fresh_id(prefix: str, taken: set) -> str:
    """The smallest unused ``<prefix><n>`` (n from 1); adds it to ``taken``.
    Deterministic, so the server's and the webapp's engines agree."""
    number = 1
    while f"{prefix}{number}" in taken:
        number += 1
    taken.add(f"{prefix}{number}")
    return f"{prefix}{number}"


def _container_member_lists(container: Any) -> List[List[str]]:
    """Mutable member lists of a container (one per tab)."""
    lists = []
    for tab in container_tabs(container):
        current = _get(tab, "fields")
        if current is None:
            current = []
            _set(tab, "fields", current)
        lists.append(current)
    return lists


def _set(obj: Any, name: str, value: Any) -> None:
    if isinstance(obj, dict):
        obj[name] = value
    else:
        setattr(obj, name, value)


def _gather_group_children(page: Any) -> set:
    children = set()
    for field in page_fields(page):
        for child in _get(_get(field, "properties"), "fields") or []:
            children.add(str(_get(child, "id")))
    return children


def repair_page(page: Any) -> int:
    """Make the page's containers valid again where that can be done without
    guessing; returns how many things changed. Drops members that no longer
    exist on the page, are internal or are a group's children (and repeated
    ones); drops a panel or field set left without questions and a strip left
    without any; a container whose members no longer follow the page's order
    is dissolved; non-members left between a container's members join it (the
    tab of the member before them). Never adds a container."""
    containers = page_containers(page)
    if not containers:
        return 0
    changed = 0
    by_id = {str(_get(f, "id")): f for f in page_fields(page)}
    seen: set = set()
    kept: List[Any] = []
    for container in containers:
        for members in _container_member_lists(container):
            valid = []
            for member in members:
                field = by_id.get(str(member))
                if field is None or _get(field, "internal") or str(member) in seen:
                    changed += 1
                    continue
                seen.add(str(member))
                valid.append(member)
            if len(valid) != len(members):
                members[:] = valid
        if not members_of(container):
            changed += 1
            continue
        kept.append(container)
    order = {fid: i for i, fid in enumerate(respondent_ids(page))}
    final: List[Any] = []
    for container in kept:
        positions = [order.get(m) for m in members_of(container)]
        if any(p is None for p in positions) or positions != sorted(positions):
            changed += 1
            continue
        final.append(container)
    if len(final) != len(containers):
        _set(_get(page, "properties"), "containers", final or None)
    for container in final:
        changed += _absorb_gaps(page, container)
    return changed


def _absorb_gaps(page: Any, container: Any) -> int:
    ids = respondent_ids(page)
    order = {fid: i for i, fid in enumerate(ids)}
    members = members_of(container)
    if len(members) < 2:
        return 0
    first, last = order[members[0]], order[members[-1]]
    taken = set(members)
    # a question of another container between them is not ours to take: the
    # two overlap, which `form_problems` reports
    changed = 0
    for fid in ids[first + 1 : last]:
        if fid in taken:
            continue
        if any(fid in members_of(other) for other in page_containers(page)):
            continue
        _join(page, container, fid, order)
        changed += 1
    return changed


def _join(page: Any, container: Any, fid: str, order: Dict[str, int]) -> None:
    """Put ``fid`` into ``container`` where its page position says: in the
    tab of the nearest member before it, after that member."""
    here = order[fid]
    best_tab = None
    best_pos = -1
    best_member = None
    for tab in container_tabs(container):
        for member in _get(tab, "fields") or []:
            pos = order.get(str(member), -1)
            if pos < here and pos > best_pos:
                best_tab, best_pos, best_member = tab, pos, member
    if best_tab is None:
        best_tab = container_tabs(container)[0]
        members = _container_member_lists_one(best_tab)
        members.insert(0, fid)
        return
    members = _container_member_lists_one(best_tab)
    members.insert(members.index(best_member) + 1, fid)


def _container_member_lists_one(tab: Any) -> List[str]:
    current = _get(tab, "fields")
    if current is None:
        current = []
        _set(tab, "fields", current)
    return current


def repair_form(form: Any) -> int:
    """``repair_page`` on every page; the number of things changed."""
    changed = 0
    for page in _get(form, "fields") or []:
        if _type_text(page) == "slide":
            changed += repair_page(page)
    return changed


def join_by_position(page: Any, fid: str) -> None:
    """After the question ``fid`` was added to the page or moved on it: it
    belongs to the container it sits strictly inside of (a member of that
    container before it and one after it), and to no other. A question that
    was the only member of its container stays in it wherever it went (the
    container follows it). At the edge of a run it is outside."""
    if not page_containers(page):
        return
    field = next((f for f in page_fields(page) if str(_get(f, "id")) == fid), None)
    if field is None:
        repair_page(page)
        return
    sole = any(members_of(c) == [fid] for c in page_containers(page))
    if sole:
        # moved to the inside of another container: it goes there instead
        order = {f: i for i, f in enumerate(respondent_ids(page))}
        here = order.get(fid, -1)
        for container in page_containers(page):
            members = members_of(container)
            if (
                members != [fid]
                and len(members) >= 2
                and order.get(members[0], here) < here < order.get(members[-1], here)
            ):
                sole = False
    if not sole:
        for container in page_containers(page):
            for members in _container_member_lists(container):
                if fid in members:
                    members.remove(fid)
    # repair drops what is gone and takes in a question left between the
    # members: that is "strictly inside"; at the edge it is outside
    repair_page(page)


def container_logic_index(form_fields: Iterable[Any]) -> Dict[str, List[Any]]:
    """``{member id: [logic of each container it is in]}`` for the logic that
    can hide (a container with usable logic only)."""
    index: Dict[str, List[Any]] = {}
    for page in form_fields or []:
        if _type_text(page) != "slide":
            continue
        for container in page_containers(page):
            logic = _get(container, "logic")
            if (
                logic is None
                or not _get(logic, "action")
                or not (_get(logic, "conditions") or [])
            ):
                continue
            for member in members_of(container):
                index.setdefault(str(member), []).append(logic)
    return index


def container_problems(
    page: Any,
    taken: Optional[set] = None,
    earlier: Optional[Iterable[str]] = None,
    item_ids: Optional[Iterable[str]] = None,
) -> List[Tuple[Optional[str], str]]:
    """Why the page's containers cannot stand, as ``(container id, message)``:
    members that are unknown, internal, a group's children or in two
    containers; members not next to each other or out of page order; ids used
    twice (``taken`` holds the ids of the pages before, and is added to);
    logic that reads a question that is not before the container's first
    member, or one of its own members, or has more than
    ``CONTAINER_CONDITIONS_MAX`` conditions; container and tab ids that are
    also the id of a question or page. ``earlier``: the ids of every question
    on the earlier pages. ``item_ids``: every page, question and group-child
    id of the form (this page's own when left out)."""
    problems: List[Tuple[Optional[str], str]] = []
    containers = page_containers(page)
    if not containers:
        return problems
    taken = taken if taken is not None else set()
    fields = {str(_get(f, "id")): f for f in page_fields(page)}
    children = _gather_group_children(page)
    ids = respondent_ids(page)
    order = {fid: i for i, fid in enumerate(ids)}
    claimed: Dict[str, str] = {}
    before_pages = set(earlier or [])
    items = set(item_ids) if item_ids is not None else page_item_ids(page)
    for container in containers:
        cid = str(_get(container, "id"))
        names = [cid]
        if _get(container, "type") == "tabs":
            names += [str(_get(tab, "id")) for tab in _get(container, "tabs") or []]
        for name in names:
            if name in taken:
                problems.append((cid, f"The id '{name}' is used more than once."))
            elif name in items:
                problems.append(
                    (cid, f"The id '{name}' is also the id of a question or page.")
                )
            taken.add(name)
        logic = _get(container, "logic")
        if len(_get(logic, "conditions") or []) > CONTAINER_CONDITIONS_MAX:
            problems.append(
                (
                    cid,
                    f"A container's rule can have at most {CONTAINER_CONDITIONS_MAX} conditions.",
                )
            )
        members = members_of(container)
        if not members:
            problems.append((cid, "A container needs at least one question."))
            continue
        if len(set(members)) != len(members):
            problems.append((cid, "A question can be listed only once in a container."))
        bad = False
        for member in members:
            if member in claimed and claimed[member] != cid:
                problems.append(
                    (
                        cid,
                        f"The question '{member}' is already in the container '{claimed[member]}'.",
                    )
                )
                bad = True
            claimed[member] = cid
            field = fields.get(member)
            if field is None:
                problems.append(
                    (
                        cid,
                        f"The question '{member}' is not on this page"
                        + (
                            " (it is inside a repeating group, which a container cannot split)."
                            if member in children
                            else "."
                        ),
                    )
                )
                bad = True
            elif _get(field, "internal"):
                problems.append(
                    (cid, f"The internal question '{member}' cannot be in a container.")
                )
                bad = True
        if bad:
            continue
        positions = [order[m] for m in members]
        if positions != list(range(positions[0], positions[0] + len(positions))):
            problems.append(
                (
                    cid,
                    "The questions of a container must be next to each other on the page, in the "
                    "order of the container; move them first (move_field).",
                )
            )
            continue
        for condition in _get(logic, "conditions") or []:
            source = str(
                _get(condition, "field_id") or _get(condition, "fieldId") or ""
            )
            if not source:
                continue
            if source in members:
                problems.append(
                    (cid, "A container's rule cannot read one of its own questions.")
                )
            elif source in order and order[source] > positions[0]:
                problems.append(
                    (
                        cid,
                        "A container's rule can only read questions before the container.",
                    )
                )
            elif source not in order and source not in before_pages:
                problems.append(
                    (cid, f"A container's rule reads the unknown question '{source}'.")
                )
    return problems


def form_problems(form: Any) -> List[Tuple[str, Optional[str], str]]:
    """``(page id, container id, message)`` for every container problem of the
    form (``container_problems`` page by page, ids unique across the form)."""
    found: List[Tuple[str, Optional[str], str]] = []
    taken: set = set()
    earlier: set = set()
    items = form_item_ids(form)
    for page in _get(form, "fields") or []:
        if _type_text(page) != "slide":
            continue
        for cid, message in container_problems(page, taken, earlier, items):
            found.append((str(_get(page, "id")), cid, message))
        for field in page_fields(page):
            earlier.add(str(_get(field, "id")))
            for child in _get(_get(field, "properties"), "fields") or []:
                earlier.add(str(_get(child, "id")))
    return found
