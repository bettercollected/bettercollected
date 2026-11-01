"""Layout containers (panels, field sets, tabs): the model, the structure
helpers (repair, membership by position), the edit operation, the spec, the
visibility a container gives its questions, and the switch
(services/layout_containers.py). The ops engines' shared cases are in
docs/spec/form-ops-v1.cases.json (test_form_ops_corpus.py); the webapp's twin of
the helpers shares docs/spec/layout-containers.cases.json."""

import json

import pytest
from common.form_spec import form_to_spec_dict, spec_to_form
from common.layout_containers import (
    form_problems,
    join_by_position,
    members_of,
    repair_form,
)
from common.models.standard_form import (
    LayoutContainer,
    StandardForm,
    StandardFormField,
)
from pydantic import ValidationError

from backend.app.services.ai.ops import apply_form_ops, parse_ops
from backend.app.services.form_spec.checks import check_spec_document
from backend.app.services.layout_containers import (
    ensure_layout_allowed,
    ensure_valid_layout,
    new_or_changed_containers,
)
from backend.app.services.repeating_groups import (
    is_hidden_by_logic,
    logic_sources,
)
from backend.app.exceptions import HTTPException
from backend.config import settings
from backend.config.application import Application


def q(field_id, **extra):
    return {"id": field_id, "type": "short_text", "title": field_id.upper(), **extra}


def form_of(*pages, containers=None):
    """A form of pages; each page is a list of questions, or a dict with
    ``fields`` and ``containers``."""
    slides = []
    for i, page in enumerate(pages):
        body = page if isinstance(page, dict) else {"fields": page}
        slides.append(
            {
                "id": f"p{i + 1}",
                "index": i,
                "type": "slide",
                "properties": body,
            }
        )
    return StandardForm.model_validate(
        {"title": "T", "builder_version": "v2", "fields": slides}
    )


def panel(cid, *ids, **extra):
    return {
        "id": cid,
        "type": "panel",
        "title": cid.upper(),
        "fields": list(ids),
        **extra,
    }


def tabs(cid, *tab_lists, **extra):
    return {
        "id": cid,
        "type": "tabs",
        "tabs": [
            {"id": f"{cid}t{i + 1}", "title": f"Tab {i + 1}", "fields": list(ids)}
            for i, ids in enumerate(tab_lists)
        ],
        **extra,
    }


def page_one(form):
    return form.fields[0]


def ids_of(form, page=0):
    return [f.id for f in form.fields[page].properties.fields]


@pytest.fixture(autouse=True)
def containers_on(monkeypatch):
    monkeypatch.setattr(settings, "LAYOUT_CONTAINERS_ENABLED", True)


# --- the model -------------------------------------------------------------------


def test_the_switch_is_off_by_default_and_registered():
    assert Application.model_fields["LAYOUT_CONTAINERS_ENABLED"].default is False
    from common.settings.inventory import all_specs

    entry = next(s for s in all_specs() if s.key == "LAYOUT_CONTAINERS_ENABLED")
    assert entry.default is False


def test_a_form_without_containers_is_valid_and_has_none():
    form = form_of([q("a"), q("b")])
    assert page_one(form).properties.containers is None
    assert form_problems(form) == []


def test_shape_rules_of_a_container():
    ok = LayoutContainer.model_validate(panel("c1", "a"))
    assert ok.title == "C1"
    for bad in (
        {"id": "c", "type": "panel", "fields": ["a"]},  # no title
        {"id": "c", "type": "panel", "title": "  ", "fields": ["a"]},
        {"id": "c", "type": "panel", "title": "T"},  # no questions
        {
            "id": "c",
            "type": "fieldset",
            "title": "T",
            "fields": ["a"],
            "collapsed": True,
        },
        {"id": "c", "type": "tabs"},
        {"id": "c", "type": "tabs", "title": "T", "tabs": [{"id": "t", "title": "A"}]},
        {
            "id": "c",
            "type": "panel",
            "title": "T",
            "fields": ["a"],
            "tabs": [{"id": "t", "title": "A"}],
        },
        {"id": "c d", "type": "panel", "title": "T", "fields": ["a"]},
        {"id": "c", "type": "panel", "title": "T‮", "fields": ["a"]},
        {"id": "c", "type": "box", "title": "T", "fields": ["a"]},
        tabs("c", ["a"], ["b"])
        | {"tabs": [{"id": "t", "title": "A"}, {"id": "t", "title": "B"}]},
    ):
        with pytest.raises(ValidationError):
            LayoutContainer.model_validate(bad)
    # an empty tab is fine; so are 8 tabs and not 9
    LayoutContainer.model_validate(tabs("c", [], ["a"]))
    LayoutContainer.model_validate(tabs("c", *[[f"x{i}"] for i in range(8)]))
    with pytest.raises(ValidationError):
        LayoutContainer.model_validate(tabs("c", *[[f"x{i}"] for i in range(9)]))


def test_only_a_page_has_containers():
    with pytest.raises(ValidationError):
        StandardFormField.model_validate(
            {
                "id": "x",
                "type": "short_text",
                "properties": {"containers": [panel("c", "a")]},
            }
        )


def test_at_most_twenty_containers_on_a_page():
    many = [panel(f"c{i}", f"q{i}") for i in range(21)]
    with pytest.raises(ValidationError):
        form_of({"fields": [q(f"q{i}") for i in range(21)], "containers": many})


# --- structure problems -----------------------------------------------------------


def problems(form):
    return [message for _, _, message in form_problems(form)]


def test_members_must_be_next_to_each_other_in_order():
    fields = [q("a"), q("b"), q("c"), q("d")]
    assert (
        problems(form_of({"fields": fields, "containers": [panel("c1", "a", "b")]}))
        == []
    )
    assert (
        problems(form_of({"fields": fields, "containers": [panel("c1", "b", "c")]}))
        == []
    )
    gap = problems(form_of({"fields": fields, "containers": [panel("c1", "a", "c")]}))
    assert gap and "next to each other" in gap[0]
    order = problems(form_of({"fields": fields, "containers": [panel("c1", "b", "a")]}))
    assert order and "next to each other" in order[0]


def test_internal_questions_do_not_count_for_adjacency_but_cannot_be_members():
    fields = [q("a"), q("office", internal=True), q("b")]
    assert (
        problems(form_of({"fields": fields, "containers": [panel("c1", "a", "b")]}))
        == []
    )
    bad = problems(
        form_of({"fields": fields, "containers": [panel("c1", "a", "office")]})
    )
    assert bad and "internal" in bad[0]


def test_ids_members_and_unknowns():
    fields = [q("a"), q("b"), q("c")]
    two = problems(
        form_of(
            {"fields": fields, "containers": [panel("c1", "a", "b"), panel("c1", "c")]}
        )
    )
    assert any("used more than once" in m for m in two)
    shared = problems(
        form_of(
            {
                "fields": fields,
                "containers": [panel("c1", "a", "b"), panel("c2", "b", "c")],
            }
        )
    )
    assert any("already in the container" in m for m in shared)
    unknown = problems(
        form_of({"fields": fields, "containers": [panel("c1", "a", "zz")]})
    )
    assert any("not on this page" in m for m in unknown)
    # an id used on another page counts too
    other = form_of(
        {"fields": fields, "containers": [panel("c1", "a")]},
        {"fields": [q("x")], "containers": [panel("c1", "x")]},
    )
    assert any("used more than once" in m for m in problems(other))


def test_a_repeating_group_is_a_member_whole_but_its_children_are_not():
    group = {
        "id": "g",
        "type": "group",
        "title": "People",
        "properties": {"repeat": {"minItems": 1, "maxItems": 3}, "fields": [q("name")]},
    }
    fields = [q("a"), group, q("b")]
    assert (
        problems(
            form_of({"fields": fields, "containers": [panel("c1", "a", "g", "b")]})
        )
        == []
    )
    child = problems(form_of({"fields": fields, "containers": [panel("c1", "name")]}))
    assert child and "repeating group" in child[0]


def test_container_logic_reads_only_earlier_questions():
    fields = [q("a"), q("b"), q("c"), q("d")]
    rule = lambda source: {  # noqa: E731
        "action": "SHOW",
        "conditions": [{"fieldId": source, "comparison": "IS_EQUAL", "value": "x"}],
    }
    ok = form_of(
        {"fields": fields, "containers": [panel("c1", "c", "d", logic=rule("a"))]}
    )
    assert problems(ok) == []
    own = problems(
        form_of(
            {"fields": fields, "containers": [panel("c1", "c", "d", logic=rule("d"))]}
        )
    )
    assert any("own questions" in m for m in own)
    later = problems(
        form_of(
            {"fields": fields, "containers": [panel("c1", "a", "b", logic=rule("c"))]}
        )
    )
    assert any("before the container" in m for m in later)
    unknown = problems(
        form_of(
            {
                "fields": fields,
                "containers": [panel("c1", "c", "d", logic=rule("nope"))],
            }
        )
    )
    assert any("unknown question" in m for m in unknown)
    # a question on an earlier page is fine
    paged = form_of(
        [q("x")],
        {
            "fields": [q("y"), q("z")],
            "containers": [panel("c1", "y", "z", logic=rule("x"))],
        },
    )
    assert problems(paged) == []


# --- repair and membership by position -------------------------------------------


def test_repair_drops_what_is_gone_and_takes_in_what_sits_between():
    fields = [q("a"), q("b"), q("c"), q("d")]
    form = form_of({"fields": fields, "containers": [panel("c1", "a", "gone", "c")]})
    assert repair_form(form) >= 1
    container = page_one(form).properties.containers[0]
    # "gone" is dropped, "b" sat between a and c and joins
    assert members_of(container) == ["a", "b", "c"]
    assert form_problems(form) == []


def test_repair_drops_an_emptied_container_and_dissolves_one_out_of_order():
    form = form_of({"fields": [q("a"), q("b")], "containers": [panel("c1", "x", "y")]})
    repair_form(form)
    assert page_one(form).properties.containers is None
    form = form_of(
        {"fields": [q("a"), q("b"), q("c")], "containers": [tabs("c1", ["c"], ["a"])]}
    )
    repair_form(form)
    assert page_one(form).properties.containers is None


def test_repair_leaves_a_tab_empty_and_a_valid_container_alone():
    form = form_of(
        {"fields": [q("a"), q("b")], "containers": [tabs("c1", ["a", "b"], [])]}
    )
    assert repair_form(form) == 0
    assert [t.fields for t in page_one(form).properties.containers[0].tabs] == [
        ["a", "b"],
        [],
    ]


def move(form, field_id, to):
    fields = page_one(form).properties.fields
    field = next(f for f in fields if f.id == field_id)
    fields.remove(field)
    fields.insert(to, field)
    join_by_position(page_one(form), field_id)


def container_ids(form, index=0):
    return members_of(page_one(form).properties.containers[index])


def test_a_moved_question_joins_the_container_it_sits_inside():
    form = form_of(
        {
            "fields": [q("x"), q("a"), q("b"), q("c"), q("y")],
            "containers": [panel("c1", "a", "b", "c")],
        }
    )
    move(form, "x", 1)  # between a and b
    assert container_ids(form) == ["a", "x", "b", "c"]
    move(form, "y", 4)  # still the end: outside
    assert container_ids(form) == ["a", "x", "b", "c"]


def test_a_member_moved_out_leaves_and_one_moved_within_stays():
    form = form_of(
        {
            "fields": [q("a"), q("b"), q("c"), q("y")],
            "containers": [panel("c1", "a", "b", "c")],
        }
    )
    move(form, "a", 3)  # past the end
    assert container_ids(form) == ["b", "c"]
    form = form_of(
        {"fields": [q("a"), q("b"), q("c")], "containers": [panel("c1", "a", "b", "c")]}
    )
    move(form, "a", 1)  # [b, a, c]: still inside
    assert container_ids(form) == ["b", "a", "c"]
    # the edge: [a, b, c] -> c to the front leaves
    move(form, "c", 0)
    assert container_ids(form) == ["b", "a"]


def test_the_first_member_moved_up_past_a_neighbour_does_not_pull_it_in():
    form = form_of(
        {"fields": [q("x"), q("a"), q("b")], "containers": [panel("c1", "a", "b")]}
    )
    move(form, "a", 0)  # [a, x, b]: a left, x is not taken in
    assert container_ids(form) == ["b"]
    assert ids_of(form) == ["a", "x", "b"]


def test_the_only_member_takes_its_container_along():
    form = form_of(
        {"fields": [q("x"), q("a"), q("y")], "containers": [panel("c1", "a")]}
    )
    move(form, "a", 2)
    assert container_ids(form) == ["a"]
    # ... unless it lands inside another container
    form = form_of(
        {
            "fields": [q("x"), q("a"), q("m"), q("n")],
            "containers": [panel("c1", "a"), panel("c2", "m", "n")],
        }
    )
    move(form, "a", 2)  # [x, m, a, n]
    assert [c.id for c in page_one(form).properties.containers] == ["c2"]
    assert container_ids(form) == ["m", "a", "n"]


def test_a_question_inserted_into_a_tab_joins_the_tab_of_the_member_before_it():
    form = form_of(
        {
            "fields": [q("a"), q("b"), q("c"), q("d")],
            "containers": [tabs("c1", ["a", "b"], ["c", "d"])],
        }
    )
    fields = page_one(form).properties.fields
    fields.insert(3, StandardFormField.model_validate(q("n")))  # between c and d
    join_by_position(page_one(form), "n")
    assert [t.fields for t in page_one(form).properties.containers[0].tabs] == [
        ["a", "b"],
        ["c", "n", "d"],
    ]


# --- the edit operation -----------------------------------------------------------


def apply(form, *ops, atomic=False):
    return apply_form_ops(form, parse_ops(list(ops)), atomic=atomic)


def containers_of(form, page=0):
    return (
        page_one(form).properties.containers
        if page == 0
        else form.fields[page].properties.containers
    )


def test_set_page_containers_sets_clears_and_makes_up_ids():
    form = form_of([q("a"), q("b"), q("c")])
    after, results = apply(
        form,
        {
            "op": "set_page_containers",
            "pageId": "p1",
            "containers": [
                {"type": "panel", "title": "Who", "fields": ["a", "b"]},
                {
                    "type": "tabs",
                    "tabs": [{"title": "One", "fields": ["c"]}, {"title": "Two"}],
                },
            ],
        },
    )
    assert all(r.ok for r in results), [r.message for r in results]
    containers = containers_of(after)
    assert [c.id for c in containers] == ["c1", "c2"]
    assert [t.id for t in containers[1].tabs] == ["t1", "t2"]
    cleared, results = apply(
        after, {"op": "set_page_containers", "pageId": "p1", "containers": None}
    )
    assert all(r.ok for r in results)
    assert containers_of(cleared) is None
    assert ids_of(cleared) == ["a", "b", "c"]


def test_set_page_containers_refuses_what_the_checks_refuse():
    form = form_of([q("a"), q("b"), q("c"), q("office", internal=True)])
    for payload, text in (
        ([{"type": "panel", "title": "x", "fields": ["a", "c"]}], "next to each other"),
        ([{"type": "panel", "title": "x", "fields": ["a", "zz"]}], "not on this page"),
        ([{"type": "panel", "title": "x", "fields": ["a", "office"]}], "internal"),
        ([{"type": "panel", "fields": ["a"]}], "needs a title"),
        ([{"type": "panel", "title": "x", "fields": []}], "at least one question"),
        ([{"type": "tabs", "tabs": []}], "at least one tab"),
        (
            [
                {"id": "k", "type": "panel", "title": "x", "fields": ["a"]},
                {"id": "k", "type": "panel", "title": "y", "fields": ["b"]},
            ],
            "unique",
        ),
        (
            [
                {
                    "type": "panel",
                    "title": "x",
                    "fields": ["a"],
                    "tabs": [{"title": "t"}],
                }
            ],
            "Only a tabs container",
        ),
    ):
        after, results = apply(
            form, {"op": "set_page_containers", "pageId": "p1", "containers": payload}
        )
        assert not results[0].ok and text in results[0].message, (
            payload,
            results[0].message,
        )
        assert containers_of(after) is None


def test_set_page_containers_takes_refs_to_questions_made_earlier():
    form = form_of([q("a")])
    after, results = apply(
        form,
        {
            "op": "add_field",
            "pageId": "p1",
            "ref": "new",
            "field": {"title": "N", "type": "short_text"},
        },
        {
            "op": "set_page_containers",
            "pageId": "p1",
            "containers": [
                {"type": "fieldset", "title": "Both", "fields": ["a", "$ref:new"]}
            ],
        },
    )
    assert all(r.ok for r in results), [r.message for r in results]
    assert len(members_of(containers_of(after)[0])) == 2


def test_ops_keep_membership_true():
    form = form_of(
        {
            "fields": [q("a"), q("b"), q("c"), q("x")],
            "containers": [panel("c1", "a", "b", "c")],
        }
    )
    # add inside joins, at the end does not
    after, _ = apply(
        form,
        {
            "op": "add_field",
            "pageId": "p1",
            "index": 1,
            "field": {"title": "N", "type": "short_text"},
        },
    )
    assert len(container_ids(after)) == 4
    after, _ = apply(
        form,
        {
            "op": "add_field",
            "pageId": "p1",
            "index": 3,
            "field": {"title": "N", "type": "short_text"},
        },
    )
    assert len(container_ids(after)) == 3
    # a removal drops the member, the last removal drops the container
    after, _ = apply(form, {"op": "remove_field", "fieldId": "b"})
    assert container_ids(after) == ["a", "c"]
    after, _ = apply(
        form,
        {"op": "remove_field", "fieldId": "a"},
        {"op": "remove_field", "fieldId": "b"},
        {"op": "remove_field", "fieldId": "c"},
    )
    assert containers_of(after) is None
    # a move out, a move to another page, making a member internal
    after, _ = apply(form, {"op": "move_field", "fieldId": "c", "index": 3})
    assert container_ids(after) == ["a", "b"]
    two = form_of(
        {
            "fields": [q("a"), q("b"), q("c")],
            "containers": [panel("c1", "a", "b", "c")],
        },
        [q("z")],
    )
    after, _ = apply(two, {"op": "move_field", "fieldId": "b", "toPageId": "p2"})
    assert container_ids(after) == ["a", "c"]
    after, _ = apply(
        form, {"op": "update_field", "fieldId": "b", "patch": {"internal": True}}
    )
    assert container_ids(after) == ["a", "c"]
    assert form_problems(after) == []


def test_removing_a_question_removes_the_container_rules_that_read_it():
    rule = {
        "action": "HIDE",
        "conditions": [{"fieldId": "a", "comparison": "IS_EQUAL", "value": "x"}],
    }
    form = form_of(
        {
            "fields": [q("a"), q("b"), q("c")],
            "containers": [panel("c1", "b", "c", logic=rule)],
        }
    )
    assert page_one(form).properties.containers[0].logic is not None
    after, results = apply(form, {"op": "remove_field", "fieldId": "a"})
    assert containers_of(after)[0].logic is None
    assert "logic" in results[0].message
    # a question a container's rule reads cannot become internal
    _, results = apply(
        form, {"op": "update_field", "fieldId": "a", "patch": {"internal": True}}
    )
    assert not results[0].ok


def test_duplicate_page_copies_containers_with_new_ids():
    form = form_of(
        {
            "fields": [q("a"), q("b")],
            "containers": [
                panel("c1", "a", "b"),
            ],
        },
    )
    after, results = apply(form, {"op": "duplicate_page", "pageId": "p1"})
    assert all(r.ok for r in results)
    copy = after.fields[1]
    assert copy.properties.containers[0].id == "c2"
    new_ids = [f.id for f in copy.properties.fields]
    assert members_of(copy.properties.containers[0]) == new_ids
    assert set(new_ids).isdisjoint({"a", "b"})
    assert form_problems(after) == []


def test_logic_hidden_container_hides_its_questions_but_keeps_what_they_hold():
    rule = {
        "action": "SHOW",
        "conditions": [
            {
                "fieldId": "gate",
                "fieldType": "short_text",
                "comparison": "IS_EQUAL",
                "value": "yes",
            }
        ],
    }
    form = form_of(
        {
            "fields": [q("gate"), q("a"), q("b"), q("c")],
            "containers": [panel("c1", "a", "b", logic=rule)],
        }
    )
    sources = logic_sources(form.fields)
    fields = {f.id: f for f in form.fields[0].properties.fields}
    shown = {"gate": {"type": "text", "text": "yes"}}
    hidden = {"gate": {"type": "text", "text": "no"}}
    assert not is_hidden_by_logic(fields["a"], shown, sources)
    assert is_hidden_by_logic(fields["a"], hidden, sources)
    assert is_hidden_by_logic(fields["b"], hidden, sources)
    assert not is_hidden_by_logic(fields["c"], hidden, sources)
    # without the sources map a container is not looked at (like choice options)
    assert not is_hidden_by_logic(fields["a"], hidden)
    # the sources map still holds only questions
    assert set(sources) == {"gate", "a", "b", "c"}


# --- the spec ---------------------------------------------------------------------


def test_the_spec_roundtrips_and_checks_containers():
    form = form_of(
        {
            "fields": [q("a"), q("b"), q("c")],
            "containers": [
                panel("c1", "a", "b", collapsed=True),
                tabs("c2", ["c"], []),
            ],
        }
    )
    document = form_to_spec_dict(form)
    page = document["pages"][0]
    assert page["containers"][0] == {
        "id": "c1",
        "type": "panel",
        "title": "C1",
        "collapsed": True,
        "fields": ["a", "b"],
    } or page["containers"][0]["fields"] == ["a", "b"]
    again = spec_to_form(
        __import__("common.form_spec", fromlist=["FormSpec"]).FormSpec.model_validate(
            document
        )
    )
    assert again.fields[0].properties.containers == form.fields[0].properties.containers
    result = check_spec_document(document)
    assert result["valid"], result["errors"]
    document["pages"][0]["containers"][0]["fields"] = ["a", "c"]
    broken = check_spec_document(document)
    assert not broken["valid"]
    assert broken["errors"][0]["path"] == "/pages/0/containers/0"
    assert "next to each other" in broken["errors"][0]["message"]


def test_the_spec_warns_while_the_switch_is_off(monkeypatch):
    monkeypatch.setattr(settings, "LAYOUT_CONTAINERS_ENABLED", False)
    form = form_of({"fields": [q("a")], "containers": [panel("c1", "a")]})
    result = check_spec_document(form_to_spec_dict(form))
    assert any("LAYOUT_CONTAINERS_ENABLED" in w["message"] for w in result["warnings"])


# --- the switch -------------------------------------------------------------------


def disabled(error):
    return (
        error.value.status_code == 422
        and error.value.content["code"] == "layout_containers_disabled"
    )


def test_what_counts_as_new_or_changed(monkeypatch):
    stored = form_of(
        {
            "fields": [q("a"), q("b"), q("c")],
            "containers": [panel("c1", "a", "b", "c", collapsed=True)],
        }
    )
    assert new_or_changed_containers(stored, stored) == []
    # fewer questions or none at all is never a change
    fewer = form_of(
        {
            "fields": [q("a"), q("b"), q("c")],
            "containers": [panel("c1", "a", "b", collapsed=True)],
        }
    )
    assert new_or_changed_containers(fewer, stored) == []
    assert new_or_changed_containers(form_of([q("a")]), stored) == []
    # more questions, another title, collapsed flag or a new container is
    wider = form_of(
        {
            "fields": [q("a"), q("b"), q("c"), q("d")],
            "containers": [panel("c1", "a", "b", "c", "d", collapsed=True)],
        }
    )
    assert new_or_changed_containers(wider, stored) == ["c1"]
    renamed = form_of(
        {
            "fields": [q("a"), q("b"), q("c")],
            "containers": [
                panel("c1", "a", "b", "c", collapsed=True) | {"title": "Other"}
            ],
        }
    )
    assert new_or_changed_containers(renamed, stored) == ["c1"]
    opened = form_of(
        {"fields": [q("a"), q("b"), q("c")], "containers": [panel("c1", "a", "b", "c")]}
    )
    assert new_or_changed_containers(opened, stored) == ["c1"]
    brand_new = form_of({"fields": [q("a")], "containers": [panel("c9", "a")]})
    assert new_or_changed_containers(brand_new, stored) == ["c9"]
    # tabs: a member moving from one tab to another is a change, taking one away is not
    old = form_of({"fields": [q("a"), q("b")], "containers": [tabs("t", ["a"], ["b"])]})
    swapped = form_of(
        {"fields": [q("a"), q("b")], "containers": [tabs("t", ["a", "b"], [])]}
    )
    assert new_or_changed_containers(swapped, old) == ["t"]
    assert (
        new_or_changed_containers(
            form_of({"fields": [q("a"), q("b")], "containers": [tabs("t", ["a"], [])]}),
            old,
        )
        == []
    )


def test_the_guard_refuses_while_off_and_passes_when_on(monkeypatch):
    form = form_of({"fields": [q("a")], "containers": [panel("c1", "a")]})
    monkeypatch.setattr(settings, "LAYOUT_CONTAINERS_ENABLED", False)
    with pytest.raises(HTTPException) as error:
        ensure_layout_allowed(form)
    assert disabled(error)
    assert "LAYOUT_CONTAINERS_ENABLED" in error.value.content["message"]
    assert error.value.content["errors"][0]["containerId"] == "c1"
    ensure_layout_allowed(form, form)
    monkeypatch.setattr(settings, "LAYOUT_CONTAINERS_ENABLED", True)
    ensure_layout_allowed(form)


def test_the_funnel_every_save_path_ends_in_checks_the_switch(monkeypatch):
    from backend.app.services.new_question_types import ensure_question_types_allowed

    form = form_of({"fields": [q("a")], "containers": [panel("c1", "a")]})
    monkeypatch.setattr(settings, "LAYOUT_CONTAINERS_ENABLED", False)
    with pytest.raises(HTTPException) as error:
        ensure_question_types_allowed(form)
    assert disabled(error)
    ensure_question_types_allowed(form, form)


def test_ops_are_refused_while_off_but_may_shrink_or_remove(monkeypatch):
    stored = form_of(
        {
            "fields": [q("a"), q("b"), q("c"), q("x")],
            "containers": [panel("c1", "a", "b", "c")],
        }
    )
    monkeypatch.setattr(settings, "LAYOUT_CONTAINERS_ENABLED", False)
    after, results = apply(
        stored,
        {
            "op": "set_page_containers",
            "pageId": "p1",
            "containers": [panel("c9", "a", "b")],
        },
    )
    assert not results[0].ok and "LAYOUT_CONTAINERS_ENABLED" in results[0].message
    assert [c.id for c in containers_of(after)] == ["c1"]
    # taking a question into the container by position is a growth: refused
    _, results = apply(
        stored,
        {
            "op": "add_field",
            "pageId": "p1",
            "index": 1,
            "field": {"title": "N", "type": "short_text"},
        },
    )
    assert not results[0].ok and "LAYOUT_CONTAINERS_ENABLED" in results[0].message
    # a question outside it is fine
    _, results = apply(
        stored,
        {
            "op": "add_field",
            "pageId": "p1",
            "field": {"title": "N", "type": "short_text"},
        },
    )
    assert results[0].ok
    # shrinking and removing are fine
    after, results = apply(stored, {"op": "remove_field", "fieldId": "b"})
    assert results[0].ok and container_ids(after) == ["a", "c"]
    after, results = apply(
        stored, {"op": "set_page_containers", "pageId": "p1", "containers": None}
    )
    assert results[0].ok and containers_of(after) is None
    # a form with no containers: any other op does not even look
    plain = form_of([q("a"), q("b")])
    _, results = apply(
        plain,
        {
            "op": "add_field",
            "pageId": "p1",
            "field": {"title": "N", "type": "short_text"},
        },
    )
    assert results[0].ok


def test_ensure_valid_layout_repairs_and_refuses():
    form = form_of(
        {
            "fields": [q("a"), q("b"), q("c")],
            "containers": [panel("c1", "a", "gone", "c")],
        }
    )
    assert ensure_valid_layout(form) >= 1
    assert members_of(page_one(form).properties.containers[0]) == ["a", "b", "c"]
    clash = form_of(
        {"fields": [q("a"), q("b")], "containers": [panel("c1", "a"), panel("c1", "b")]}
    )
    with pytest.raises(HTTPException) as error:
        ensure_valid_layout(clash)
    assert (
        error.value.status_code == 422
        and error.value.content["code"] == "invalid_layout"
    )
    assert error.value.content["errors"][0]["pageId"] == "p1"


# --- guards: moves, ids and the size of a rule ------------------------------------

RULE_ON_A = {
    "action": "SHOW",
    "operator": "AND",
    "conditions": [{"fieldId": "a", "comparison": "IS_EQUAL", "value": "x"}],
}


def guarded_form():
    """A page ``a b [c d] e`` whose panel shows when ``a`` says so."""
    return form_of(
        {
            "fields": [q("a"), q("b"), q("c"), q("d"), q("e")],
            "containers": [panel("c1", "c", "d", logic=RULE_ON_A)],
        }
    )


def test_a_move_that_would_break_a_container_rule_is_refused_and_leaves_no_trace():
    form = guarded_form()
    before = form.model_dump(mode="json")
    for op, text in (
        # the question the rule reads goes below the container
        (
            {"op": "move_field", "fieldId": "a", "index": 4},
            "can only read questions before",
        ),
        # ... or inside it, where it becomes one of its own questions
        (
            {"op": "move_field", "fieldId": "a", "index": 2},
            "cannot read one of its own",
        ),
    ):
        after, results = apply(form, op, atomic=True)
        assert not results[0].ok
        assert "would break a layout container" in results[0].message, results[
            0
        ].message
        assert text in results[0].message
        assert after.model_dump(mode="json") == before
    # the engine's own copy is untouched too: a partial batch carries on
    after, results = apply(
        form,
        {"op": "move_field", "fieldId": "a", "index": 4},
        {"op": "move_field", "fieldId": "b", "index": 4},
    )
    assert [r.ok for r in results] == [False, True]
    assert ids_of(after) == ["a", "c", "d", "e", "b"]
    assert members_of(containers_of(after)[0]) == ["c", "d"]
    assert containers_of(after)[0].logic is not None


def test_a_move_the_rule_does_not_care_about_still_applies():
    form = guarded_form()
    # out of the container: the rule goes with the container, which keeps c
    after, results = apply(form, {"op": "move_field", "fieldId": "d", "index": 0})
    assert all(r.ok for r in results)
    assert members_of(containers_of(after)[0]) == ["c"]
    # the rule's question moved up, still before the container
    after, results = apply(form, {"op": "move_field", "fieldId": "b", "index": 0})
    assert all(r.ok for r in results)
    assert form_problems(after) == []


def test_a_move_in_a_form_that_already_has_a_problem_is_not_blamed_for_it():
    form = guarded_form()
    # a rule that reads a question that does not exist: stored as it was
    containers_of(form)[0].logic.conditions.append(
        containers_of(form)[0]
        .logic.conditions[0]
        .model_copy(update={"field_id": "gone"})
    )
    assert form_problems(form)
    _, results = apply(form, {"op": "move_field", "fieldId": "b", "index": 4})
    assert results[0].ok


def test_a_page_move_that_would_break_a_container_rule_is_refused():
    form = form_of(
        [q("a")],
        {
            "fields": [q("b"), q("c")],
            "containers": [panel("c1", "b", "c", logic=RULE_ON_A)],
        },
        [q("z")],
    )
    before = form.model_dump(mode="json")
    for page_id, index in (("p1", 2), ("p2", 0)):
        after, results = apply(
            form, {"op": "move_page", "pageId": page_id, "index": index}, atomic=True
        )
        assert not results[0].ok
        assert "would break a layout container" in results[0].message
        assert after.model_dump(mode="json") == before
    after, results = apply(form, {"op": "move_page", "pageId": "p3", "index": 0})
    assert results[0].ok


def test_a_container_or_tab_id_is_never_the_id_of_a_question_or_page():
    fields = [q("a"), q("b"), q("c1")]
    clash = problems(form_of({"fields": fields, "containers": [panel("c1", "a", "b")]}))
    assert any("also the id of a question or page" in m for m in clash)
    group = {
        "id": "g",
        "type": "group",
        "title": "People",
        "properties": {"repeat": {"minItems": 1, "maxItems": 3}, "fields": [q("t1")]},
    }
    tab_clash = problems(
        form_of(
            {
                "fields": [q("a"), group],
                "containers": [
                    {
                        "id": "k",
                        "type": "tabs",
                        "tabs": [{"id": "t1", "title": "One", "fields": ["a"]}],
                    }
                ],
            }
        )
    )
    assert any("also the id of a question or page" in m for m in tab_clash)
    page_clash = problems(
        form_of(
            {"fields": [q("a"), q("b")], "containers": [panel("p2", "a", "b")]},
            [q("x")],
        )
    )
    assert any("also the id of a question or page" in m for m in page_clash)
    with pytest.raises(HTTPException) as error:
        ensure_valid_layout(
            form_of({"fields": fields, "containers": [panel("c1", "a", "b")]})
        )
    assert error.value.content["code"] == "invalid_layout"


def test_made_up_ids_and_page_copies_skip_the_ids_of_questions():
    form = form_of([q("c1"), q("t1"), q("x")])
    after, results = apply(
        form,
        {
            "op": "set_page_containers",
            "pageId": "p1",
            "containers": [
                {
                    "type": "tabs",
                    "tabs": [
                        {"title": "One", "fields": ["c1"]},
                        {"title": "Two", "fields": ["t1"]},
                    ],
                },
                {"type": "panel", "title": "Rest", "fields": ["x"]},
            ],
        },
    )
    assert results[0].ok, results[0].message
    ids = [c.id for c in containers_of(after)]
    assert ids == ["c2", "c3"]
    assert [t.id for t in containers_of(after)[0].tabs] == ["t2", "t3"]
    assert form_problems(after) == []
    # a question named like the next free id
    form = form_of(
        {"fields": [q("a"), q("b")], "containers": [panel("c1", "a", "b")]},
        [q("c2")],
    )
    after, results = apply(form, {"op": "duplicate_page", "pageId": "p1"})
    assert results[0].ok
    assert after.fields[1].properties.containers[0].id == "c3"
    assert form_problems(after) == []
    refused = apply(
        form_of([q("a")]),
        {
            "op": "set_page_containers",
            "pageId": "p1",
            "containers": [{"id": "a", "type": "panel", "title": "A", "fields": ["a"]}],
        },
        atomic=True,
    )[1]
    assert not refused[0].ok and "also the id" in refused[0].message


def test_a_container_rule_has_a_cap_on_its_conditions():
    def rule(n):
        return {
            "action": "SHOW",
            "operator": "OR",
            "conditions": [
                {"fieldId": "a", "comparison": "IS_EQUAL", "value": str(i)}
                for i in range(n)
            ],
        }

    LayoutContainer.model_validate(panel("c1", "b", logic=rule(20)))
    with pytest.raises(ValidationError, match="at most 20 conditions"):
        LayoutContainer.model_validate(panel("c1", "b", logic=rule(21)))
    # the structure check says it too, for a container built without the model
    page = StandardFormField.model_validate(
        {
            "id": "p1",
            "type": "slide",
            "properties": {"fields": [q("a"), q("b")]},
        }
    )
    page.properties.containers = [
        LayoutContainer.model_construct(
            **{
                **panel("c1", "b"),
                "logic": {"action": "SHOW", "conditions": rule(21)["conditions"]},
            }
        )
    ]
    from common.layout_containers import container_problems

    assert any("at most 20 conditions" in m for _, m in container_problems(page))
    after, results = apply(
        form_of([q("a"), q("b"), q("c")]),
        {
            "op": "set_page_containers",
            "pageId": "p1",
            "containers": [
                {"type": "panel", "title": "T", "fields": ["b", "c"], "logic": rule(21)}
            ],
        },
        atomic=True,
    )
    assert not results[0].ok and "at most 20 conditions" in results[0].message


# --- the paths a save goes through (database) -------------------------------------


def _body(*pages):
    from backend.app.controllers.workspace_forms import _parse_form_body

    slides = []
    for i, page in enumerate(pages):
        body = page if isinstance(page, dict) else {"fields": page}
        slides.append({"id": f"p{i + 1}", "type": "slide", "properties": body})
    return _parse_form_body(
        json.dumps({"title": "T", "builderVersion": "v2", "fields": slides})
    )


GROUPED = {"fields": [q("a"), q("b"), q("c")], "containers": [panel("c1", "a", "b")]}
PLAIN = [q("a"), q("b"), q("c")]


async def test_a_builder_save_follows_the_switch(workspace, monkeypatch):
    from backend.app.container import container
    from tests.app.controllers.data import testUser

    service = container.workspace_form_service()
    monkeypatch.setattr(settings, "LAYOUT_CONTAINERS_ENABLED", False)
    with pytest.raises(HTTPException) as error:
        await service.create_form(workspace.id, _body(GROUPED), testUser)
    assert disabled(error)
    plain = await service.create_form(workspace.id, _body(PLAIN), testUser)
    with pytest.raises(HTTPException) as error:
        await service.update_form(workspace.id, plain.form_id, _body(GROUPED), testUser)
    assert disabled(error)
    monkeypatch.setattr(settings, "LAYOUT_CONTAINERS_ENABLED", True)
    await service.update_form(workspace.id, plain.form_id, _body(GROUPED), testUser)
    stored = await container.form_repo().get_form_document_by_id(str(plain.form_id))
    assert members_of(stored.fields[0].properties.containers[0]) == ["a", "b"]
    # off again: the stored container is kept, re-sent unchanged, and may shrink or go
    monkeypatch.setattr(settings, "LAYOUT_CONTAINERS_ENABLED", False)
    await service.update_form(workspace.id, plain.form_id, _body(GROUPED), testUser)
    smaller = {"fields": GROUPED["fields"], "containers": [panel("c1", "a")]}
    await service.update_form(workspace.id, plain.form_id, _body(smaller), testUser)
    renamed = {
        "fields": GROUPED["fields"],
        "containers": [panel("c1", "a") | {"title": "New"}],
    }
    with pytest.raises(HTTPException) as error:
        await service.update_form(workspace.id, plain.form_id, _body(renamed), testUser)
    assert disabled(error)
    await service.update_form(workspace.id, plain.form_id, _body(PLAIN), testUser)


async def test_a_builder_save_repairs_dangling_members_and_refuses_a_real_error(
    workspace, monkeypatch
):
    from backend.app.container import container
    from tests.app.controllers.data import testUser

    service = container.workspace_form_service()
    created = await service.create_form(workspace.id, _body(GROUPED), testUser)
    # a client that did not know containers removed question "b" and kept the list
    stale = {"fields": [q("a"), q("c")], "containers": [panel("c1", "a", "b")]}
    await service.update_form(workspace.id, created.form_id, _body(stale), testUser)
    stored = await container.form_repo().get_form_document_by_id(str(created.form_id))
    assert members_of(stored.fields[0].properties.containers[0]) == ["a"]
    # one that left a question between members: it is taken in
    gap = {
        "fields": [q("a"), q("x"), q("b"), q("c")],
        "containers": [panel("c1", "a", "b")],
    }
    await service.update_form(workspace.id, created.form_id, _body(gap), testUser)
    stored = await container.form_repo().get_form_document_by_id(str(created.form_id))
    assert members_of(stored.fields[0].properties.containers[0]) == ["a", "x", "b"]
    clash = {"fields": PLAIN, "containers": [panel("c1", "a"), panel("c1", "b")]}
    with pytest.raises(HTTPException) as error:
        await service.update_form(workspace.id, created.form_id, _body(clash), testUser)
    assert (
        error.value.status_code == 422
        and error.value.content["code"] == "invalid_layout"
    )


async def test_persist_form_is_the_last_gate_for_every_op_writer(
    workspace, monkeypatch
):
    from backend.app.container import container
    from backend.app.services.form_writes import persist_form
    from tests.app.controllers.data import testUser

    monkeypatch.setattr(settings, "LAYOUT_CONTAINERS_ENABLED", False)
    service = container.workspace_form_service()
    created = await service.create_form(workspace.id, _body(PLAIN), testUser)
    repo = container.form_repo()
    document = await repo.get_form_document_by_id(str(created.form_id))
    with pytest.raises(HTTPException) as error:
        await persist_form(repo, document, _body(GROUPED), parts=["fields"])
    assert disabled(error)
    monkeypatch.setattr(settings, "LAYOUT_CONTAINERS_ENABLED", True)
    assert await persist_form(repo, document, _body(GROUPED), parts=["fields"])


async def test_templates_follow_the_switch(workspace, monkeypatch):
    from backend.app.container import container
    from backend.app.models.template import StandardFormTemplate
    from tests.app.controllers.data import testUser

    body = StandardFormTemplate(title="T", fields=_body(GROUPED).fields)
    templates = container.form_template_service()
    monkeypatch.setattr(settings, "LAYOUT_CONTAINERS_ENABLED", False)
    with pytest.raises(HTTPException) as error:
        await templates.create_new_template(workspace.id, None, None, testUser, body)
    assert disabled(error)
    monkeypatch.setattr(settings, "LAYOUT_CONTAINERS_ENABLED", True)
    created = await templates.create_new_template(
        workspace.id, None, None, testUser, body
    )
    assert members_of(created.fields[0].properties.containers[0]) == ["a", "b"]


async def test_a_hidden_container_exempts_its_questions_from_required_and_keeps_their_answers(
    workspace, monkeypatch
):
    from backend.app.container import container
    from backend.app.models.dtos.response_dtos import StandardFormResponseCamelModel
    from tests.app.controllers.data import testUser

    rule = {
        "action": "SHOW",
        "conditions": [
            {
                "fieldId": "gate",
                "fieldType": "short_text",
                "comparison": "IS_EQUAL",
                "value": "yes",
            }
        ],
    }
    fields = [q("gate"), q("a", validations={"required": True}), q("b")]
    page = {"fields": fields, "containers": [panel("c1", "a", "b", logic=rule)]}
    service = container.workspace_form_service()
    created = await service.create_form(workspace.id, _body(page), testUser)
    await service.publish_form(workspace.id, created.form_id, testUser)
    text = lambda value: {"type": "text", "text": value}  # noqa: E731
    # the container is shown and "a" is required
    with pytest.raises(HTTPException) as error:
        await service.submit_response(
            workspace.id,
            created.form_id,
            StandardFormResponseCamelModel(answers={"gate": text("yes")}),
            testUser,
        )
    assert error.value.content["errors"] == [{"fieldId": "a", "rule": "required"}]
    # hidden: the required question is not required, and what it holds stays stored
    response = await service.submit_response(
        workspace.id,
        created.form_id,
        StandardFormResponseCamelModel(answers={"gate": text("no"), "b": text("kept")}),
        testUser,
    )
    # accepted: the answer typed into the hidden container's question is not refused
    assert response is not None


async def test_the_permissions_answer_tells_the_builder(
    client, workspace, test_user_cookies, monkeypatch
):
    url = f"/api/v1/workspaces/{workspace.id}/permissions"
    monkeypatch.setattr(settings, "LAYOUT_CONTAINERS_ENABLED", False)
    assert (await client.get(url, cookies=test_user_cookies)).json()[
        "layoutContainersEnabled"
    ] is False
    monkeypatch.setattr(settings, "LAYOUT_CONTAINERS_ENABLED", True)
    assert (await client.get(url, cookies=test_user_cookies)).json()[
        "layoutContainersEnabled"
    ] is True


def test_the_assistant_is_told_about_containers_only_while_they_are_on(monkeypatch):
    from backend.app.services.ai.prompt_builder import ops_guide, project_form

    monkeypatch.setattr(settings, "LAYOUT_CONTAINERS_ENABLED", False)
    assert "set_page_containers" not in ops_guide()
    monkeypatch.setattr(settings, "LAYOUT_CONTAINERS_ENABLED", True)
    assert "set_page_containers" in ops_guide()
    snapshot = json.loads(
        project_form(form_of({"fields": [q("a")], "containers": [panel("c1", "a")]}))
    )
    assert snapshot["pages"][0]["containers"][0]["id"] == "c1"


# --- the cases shared with the webapp (docs/spec/layout-containers.cases.json) ---


def _shared_cases():
    from pathlib import Path

    path = (
        Path(__file__).resolve().parents[4]
        / "docs"
        / "spec"
        / "layout-containers.cases.json"
    )
    return json.loads(path.read_text("utf-8"))["cases"]


def _shared_page(spec, page_id="p1"):
    """A page as the cases write it: fields are ids, {id, internal} or {id, group}."""
    from common.models.standard_form import LayoutTab

    fields = []
    for item in spec["fields"]:
        if isinstance(item, str):
            fields.append(q(item))
        elif "group" in item:
            fields.append(
                {
                    "id": item["id"],
                    "type": "group",
                    "title": item["id"],
                    "properties": {
                        "repeat": {"minItems": 1, "maxItems": 3},
                        "fields": [q(c) for c in item["group"]],
                    },
                }
            )
        else:
            fields.append(
                q(item["id"], **({"internal": True} if item.get("internal") else {}))
            )
    page = StandardFormField.model_validate(
        {"id": page_id, "type": "slide", "properties": {"fields": fields}}
    )
    if spec.get("containers") is not None:
        # built without validation: a case may break the rules on purpose
        page.properties.containers = [
            LayoutContainer.model_construct(
                **{
                    **c,
                    **(
                        {"tabs": [LayoutTab.model_construct(**t) for t in c["tabs"]]}
                        if c.get("tabs")
                        else {}
                    ),
                }
            )
            for c in spec["containers"]
        ]
    return page


def _dumped(containers):
    if not containers:
        return None
    return [
        c.model_dump(mode="json", by_alias=True, exclude_none=True) for c in containers
    ]


@pytest.mark.parametrize("case", _shared_cases(), ids=lambda case: case["name"])
def test_the_shared_structure_cases(case):
    from common.layout_containers import repair_page

    if case["kind"] == "repair":
        page = _shared_page(case["page"])
        changed = repair_page(page)
        assert {
            "containers": _dumped(page.properties.containers),
            "changed": changed,
        } == case["expect"]
    elif case["kind"] == "join":
        page = _shared_page(case["page"])
        join_by_position(page, case["fieldId"])
        assert {"containers": _dumped(page.properties.containers)} == case["expect"]
    else:
        pages = [
            _shared_page(spec, f"p{i + 1}") for i, spec in enumerate(case["pages"])
        ]
        form = StandardForm.model_construct(fields=pages)
        found = [
            {"pageId": page_id, "containerId": container_id, "message": message}
            for page_id, container_id, message in form_problems(form)
        ]
        assert {"problems": found} == case["expect"]


# --- titles, ids, the import path and copies ------------------------------------


def test_a_title_keeps_the_joiners_of_emoji_and_scripts_but_no_other_format_character():
    for title in ("Team \U0001f469‍\U0001f4bb", "می‌خواهم", "क्‍ष"):
        assert (
            LayoutContainer.model_validate(panel("c", "a") | {"title": title}).title
            == title
        )
    for bad in ("T‮", "T​", "T﻿", "T⁦", "T\x07"):
        with pytest.raises(ValidationError):
            LayoutContainer.model_validate(panel("c", "a") | {"title": bad})
    LayoutContainer.model_validate(
        tabs("c", ["a"]) | {"tabs": [{"id": "t", "title": "می‌خواهم", "fields": ["a"]}]}
    )
    with pytest.raises(ValidationError):
        LayoutContainer.model_validate(
            tabs("c", ["a"]) | {"tabs": [{"id": "t", "title": "A‮", "fields": ["a"]}]}
        )


def test_a_member_id_is_bounded():
    with pytest.raises(ValidationError):
        LayoutContainer.model_validate(panel("c", "x" * 201))
    LayoutContainer.model_validate(panel("c", "x" * 200))


def _converted(page):
    return {
        "form": {
            "form_id": "1FAIpQLSe-layout-import",
            "title": "Imported form",
            "settings": {"provider": "google"},
            "fields": [{"id": "p1", "type": "slide", "properties": page}],
        },
        "responses": [],
    }


async def test_an_import_goes_through_the_layout_checks(workspace, monkeypatch):
    from backend.app.container import container

    importer = container.form_import_service()
    page = {"fields": [q("a"), q("b")], "containers": [panel("c1", "a", "gone", "b")]}
    monkeypatch.setattr(settings, "LAYOUT_CONTAINERS_ENABLED", False)
    with pytest.raises(HTTPException) as error:
        await importer.save_converted_form_and_responses(
            _converted(page), None, workspace_id=workspace.id
        )
    assert disabled(error)
    monkeypatch.setattr(settings, "LAYOUT_CONTAINERS_ENABLED", True)
    await importer.save_converted_form_and_responses(
        _converted(page), None, workspace_id=workspace.id
    )
    stored = await container.form_repo().get_form_document_by_id(
        "1FAIpQLSe-layout-import"
    )
    # the member that is not there was repaired away
    assert members_of(stored.fields[0].properties.containers[0]) == ["a", "b"]


async def test_a_copy_of_a_form_keeps_its_containers_while_the_switch_is_off(
    workspace, monkeypatch
):
    from backend.app.container import container
    from tests.app.controllers.data import testUser

    service = container.workspace_form_service()
    created = await service.create_form(workspace.id, _body(GROUPED), testUser)
    stored = await container.form_repo().get_form_document_by_id(str(created.form_id))
    monkeypatch.setattr(settings, "LAYOUT_CONTAINERS_ENABLED", False)
    copy = StandardForm(**stored.model_dump())
    copied = await service.create_form(
        workspace.id, copy, testUser, drop_unusable_settings=True
    )
    again = await container.form_repo().get_form_document_by_id(str(copied.form_id))
    assert members_of(again.fields[0].properties.containers[0]) == ["a", "b"]
    # a new form with the same containers is refused
    with pytest.raises(HTTPException) as error:
        await service.create_form(
            workspace.id, StandardForm(**stored.model_dump()), testUser
        )
    assert disabled(error)
