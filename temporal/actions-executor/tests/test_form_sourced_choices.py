"""A choice answer to a question whose options come from a list or another
form's answers is written as the label stored beside the chosen id (the
options are not part of the form), never as the id."""

from utilities.form import get_answer_for_field

SOURCED = {
    "id": "who",
    "type": "dropdown",
    "properties": {"option_source": {"kind": "list"}},
}
SOURCED_MANY = {
    "id": "whom",
    "type": "multiple_choice",
    "properties": {"option_source": {"kind": "form_answers"}, "allow_multiple_selection": True},
}
STATIC = {
    "id": "plain",
    "type": "dropdown",
    "properties": {"choices": [{"id": "c1", "value": "Red"}]},
}


def test_a_single_choice_is_its_label_and_an_other_text():
    answers = {"who": {"choice": {"value": "li1", "label": "Alice Example"}}}
    assert get_answer_for_field({"answers": answers}, SOURCED) == "Alice Example"
    other = {"who": {"choice": {"value": "li1", "label": "Alice", "other": "Else"}}}
    assert get_answer_for_field({"answers": other}, SOURCED) == "Alice, Else"
    assert get_answer_for_field({"answers": {}}, SOURCED) == ""


def test_a_multiple_choice_is_its_labels_in_the_order_chosen():
    answers = {
        "whom": {
            "choices": {
                "values": ["fa2", "fa1"],
                "labels": {"fa1": "Bob", "fa2": "Carol"},
            }
        }
    }
    assert get_answer_for_field({"answers": answers}, SOURCED_MANY) == "Carol, Bob"


def test_a_static_question_still_reads_its_options():
    answers = {"plain": {"choice": {"value": "c1", "label": "Forged"}}}
    assert get_answer_for_field({"answers": answers}, STATIC) == "Red"
