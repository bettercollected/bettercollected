import copy

from smoke import forms


def stored(responses):
    """Answers as the API returns them (types as the product stores them)."""
    out = []
    for values in responses:
        out.append(
            {
                "answers": {
                    "name": {"type": "text", "text": values["name"]},
                    "about": {"type": "text", "text": values["about"]},
                    "mail": {"type": "email", "email": values["mail"]},
                    "count": {"type": "number", "number": values["count"]},
                    "colour": {
                        "type": "choice",
                        "choice": {
                            "value": forms.choice_id("colour", values["colour"])
                        },
                    },
                    "agree": {"type": "boolean", "boolean": values["agree"] == "Yes"},
                }
            }
        )
    return out


def test_the_standing_set_reads_back():
    assert forms.compare_standing(stored(forms.STANDING_RESPONSES)) == []
    # in any order, numbers as numbers or text
    reordered = list(reversed(stored(forms.STANDING_RESPONSES)))
    reordered[0]["answers"]["count"]["number"] = 3
    assert forms.compare_standing(reordered) == []


def test_an_undecryptable_response_reads_as_empty_and_fails():
    responses = stored(forms.STANDING_RESPONSES)
    responses[1]["answers"] = {}
    problems = forms.compare_standing(responses)
    assert "response 2 has no readable answers" in problems
    assert "standing response 2 is missing" in problems


def test_a_changed_value_is_named_by_field_never_by_value():
    changed = copy.deepcopy(forms.STANDING_RESPONSES)
    changed[0]["about"] = "Something else entirely"
    changed[2]["colour"] = "Green"
    problems = forms.compare_standing(stored(changed))
    assert problems == [
        "standing response 1 differs in: about",
        "standing response 3 differs in: colour",
    ]
    assert not any("Something" in p or "Green" in p for p in problems)


def test_missing_and_extra_responses():
    responses = stored(forms.STANDING_RESPONSES[:2])
    assert forms.compare_standing(responses) == ["standing response 3 is missing"]
    duplicated = stored(forms.STANDING_RESPONSES + forms.STANDING_RESPONSES[:1])
    assert forms.compare_standing(duplicated) == [
        "response 4 repeats a standing response"
    ]


def test_answer_values():
    assert forms.answer_value({"phone_number": "+31600000000"}) == "+31600000000"
    assert forms.answer_value({"number": 2.5}) == "2.5"
    assert forms.answer_value({"number": "7"}) == "7"
    assert forms.answer_value({"choices": {"values": ["a", "b"]}}) == "a, b"
    assert forms.answer_value({"boolean": True}) == "Yes"
    assert forms.answer_value("ciphertext") is None


def test_specs_are_valid_documents():
    spec = forms.standing_spec()
    ids = [f["id"] for f in spec["pages"][0]["fields"]]
    assert ids == [f[0] for f in forms.STANDING_FIELDS]
    mail = next(f for f in spec["pages"][0]["fields"] if f["type"] == "email")
    assert mail["whyWeAsk"]
    colour = next(f for f in spec["pages"][0]["fields"] if f["id"] == "colour")
    assert [c["id"] for c in colour["choices"]] == ["colour-blue", "colour-green"]
    run = forms.run_spec("smoke-1")
    assert run["title"] == forms.run_title("smoke-1")
    assert run["trust"]["purpose"]
