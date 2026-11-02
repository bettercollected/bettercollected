from backend.app.services.builtin_actions.mapping import all_questions_mapping

FORM = {
    "hidden_fields": ["utm"],
    "fields": [
        {
            "id": "s",
            "type": "slide",
            "properties": {
                "fields": [
                    {"id": "name", "type": "short_text", "title": "Name"},
                    {"id": "name-2", "type": "short_text", "title": "Name 2"},
                    {"id": "name_2", "type": "short_text", "title": "Name 3"},
                    {"id": "doc", "type": "file_upload", "title": "File"},
                    {"id": "secret", "type": "short_text", "title": "S", "internal": True},
                    {"id": "9x", "type": "short_text", "title": "Starts with a digit"},
                    {"id": "statement", "type": "statement", "title": "Read"},
                    {"id": "answers", "type": "short_text", "title": "Named like a built-in"},
                    {
                        "id": "grp",
                        "type": "group",
                        "title": "G",
                        "properties": {
                            "repeat": {"maxItems": 2},
                            "fields": [{"id": "c", "type": "short_text", "title": "C"}],
                        },
                    },
                ]
            },
        }
    ],
}


def test_every_question_a_webhook_can_send_in_form_order():
    assert all_questions_mapping(FORM) == [
        # hidden fields first, as the form's variables list them
        ("utm", "utm"),
        ("name", "name"),
        ("name-2", "name_2"),
        # the same key again: made unique
        ("name_2", "name_2_2"),
        # a file, an internal field, a statement and an id that cannot start a key
        # (a digit) are left out; a group is one value, its items are not listed alone
        ("answers", "answers"),
        ("grp", "grp"),
    ]


def test_reserved_names_are_never_a_key():
    mapping = all_questions_mapping(FORM, reserved=("answers", "form_title"))
    assert ("answers", "answers_2") in mapping
    assert "answers" not in {key for _source, key in mapping}


def test_the_form_is_not_changed():
    import copy

    before = copy.deepcopy(FORM)
    all_questions_mapping(FORM)
    assert FORM == before
