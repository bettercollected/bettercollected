from backend.app.services.builtin_actions.links import responses_link


def test_the_responses_link_of_a_form():
    assert responses_link("https://app.example.org/", "acme", "65b0f1") == (
        "https://app.example.org/acme/dashboard/forms/65b0f1/?view=Responses"
    )


def test_a_name_or_an_id_cannot_end_the_path_or_close_a_chat_link():
    link = responses_link("https://app.example.org", "a|b>c d/../x", "f?1#2")
    assert link == (
        "https://app.example.org/a%7Cb%3Ec%20d%2F..%2Fx/dashboard/forms/f%3F1%232/?view=Responses"
    )
    assert "|" not in link and ">" not in link and " " not in link
