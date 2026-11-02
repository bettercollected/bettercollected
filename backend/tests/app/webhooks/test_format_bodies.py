"""The bodies of the legacy webhook, Slack and Discord formats
(``services/webhooks/formats.py``): what the built-in actions posted before they
moved into webhooks. Pure functions; the bytes are pinned as literals."""

import json

import pytest

from backend.app.services.webhooks import formats, guard

FORM = {
    "form_id": "65b0000000000000000000f1",
    "title": "Intake",
    "fields": [
        {
            "id": "s1",
            "type": "slide",
            "properties": {
                "fields": [
                    {"id": "name", "type": "short_text", "title": "Your name"},
                    {"id": "age", "type": "number", "title": "Age"},
                    {"id": "note", "type": "long_text", "title": "Note"},
                    {"id": "ok", "type": "yes_no", "title": "Agree?"},
                    {"id": "office", "type": "short_text", "title": "Office", "internal": True},
                ]
            },
        }
    ],
}
RESPONSE = {
    "response_id": "r1",
    "answers": {
        "name": {"text": "Zoë"},
        "age": {"number": 0},
        "note": {"text": ""},
        "ok": {"boolean": True},
        "office": {"text": "never"},
    },
}


def test_the_legacy_list_is_the_executors_bytes():
    assert formats.legacy_list_body(FORM, RESPONSE) == (
        b'[{"field_id": "name", "title": "Your name", "answer": "Zo\\u00eb"}, '
        b'{"field_id": "age", "title": "Age", "answer": 0}, '
        b'{"field_id": "note", "title": "Note", "answer": ""}, '
        b'{"field_id": "ok", "title": "Agree?", "answer": "Yes"}]'
    )


def test_slack_is_the_executors_message_with_dashes_for_empty_answers():
    body = formats.slack_body(
        FORM, RESPONSE, workspace_name="acme", client_url="https://app.example.org"
    )
    assert body == json.dumps(
        {
            "attachments": [
                {
                    "title": "🎉 **Congratulations!** You received a new response on! `Intake`\n\n",
                    "color": "#00FF00",
                    "text": "Click <https://app.example.org/acme/dashboard/forms/65b0000000000000000000f1/?view=Responses|here> to view the form response.\n\nDetails:\n",
                    "fields": [
                        {"title": "Your name", "value": "Zoë", "short": False},
                        # a falsy answer (0, empty) is a dash, as before
                        {"title": "Age", "value": "—", "short": False},
                        {"title": "Note", "value": "—", "short": False},
                        {"title": "Agree?", "value": "Yes", "short": False},
                    ],
                    "footer": "Thank you for using Bettercollected",
                }
            ]
        }
    ).encode()


def test_discord_is_the_executors_message_cut_to_discords_limits():
    body = json.loads(
        formats.discord_body(
            FORM, RESPONSE, workspace_name="acme", client_url="https://app.example.org/"
        )
    )
    assert body["content"] == "🎉 **Congratulations!** You received a new response on **Intake**"
    (embed,) = body["embeds"]
    assert embed["color"] == 0x00FF00
    assert embed["description"] == (
        "[View Form response here](https://app.example.org/acme/dashboard/forms/"
        "65b0000000000000000000f1/?view=Responses)\n--------------------------"
    )
    assert embed["footer"] == {"text": "Thank You for using Bettercollected"}
    assert embed["fields"] == [
        {"name": "Your name", "value": "Zoë", "inline": False},
        {"name": "Age", "value": "0", "inline": False},  # 0 is an answer here
        {"name": "Note", "value": "—", "inline": False},
        {"name": "Agree?", "value": "Yes", "inline": False},
    ]


def test_discord_limits_25_fields_256_names_1024_values():
    many = {
        "form_id": "f",
        "title": "Big",
        "fields": [
            {
                "id": "s",
                "type": "slide",
                "properties": {
                    "fields": [
                        {"id": f"q{i}", "type": "short_text", "title": f"  Q{i}" + "x" * 300}
                        for i in range(30)
                    ]
                },
            }
        ],
    }
    answers = {f"q{i}": {"text": "y" * 2000} for i in range(30)}
    body = json.loads(
        formats.discord_body(
            many, {"response_id": "r", "answers": answers}, workspace_name="w", client_url=""
        )
    )
    fields = body["embeds"][0]["fields"]
    assert len(fields) == 25
    assert all(len(f["name"]) <= 256 and len(f["value"]) == 1024 for f in fields)
    assert fields[0]["name"].startswith("Q0x")  # stripped before it is cut


def test_the_link_cannot_be_broken_out_of_by_a_workspace_name():
    body = formats.slack_body(
        FORM, RESPONSE, workspace_name="a|b>c d", client_url="https://app.example.org"
    )
    text = json.loads(body)["attachments"][0]["text"]
    assert "a%7Cb%3Ec%20d" in text and "a|b" not in text


def test_internal_fields_never_reach_any_format():
    for build in (
        lambda: formats.legacy_list_body(FORM, RESPONSE),
        lambda: formats.slack_body(FORM, RESPONSE, workspace_name="w", client_url="https://x"),
        lambda: formats.discord_body(FORM, RESPONSE, workspace_name="w", client_url="https://x"),
    ):
        assert b"never" not in build() and b"Office" not in build()


def test_a_test_event_has_every_title_and_no_answer():
    body = json.loads(formats.legacy_list_body(FORM, formats.empty_response()))
    assert [e["title"] for e in body] == ["Your name", "Age", "Note", "Agree?"]
    assert [e["answer"] for e in body] == [None, None, None, ""]


@pytest.mark.parametrize(
    "format_, url, allowed",
    [
        ("slack", "https://hooks.slack.com/services/T0/B0/xyz", True),
        ("slack", "https://hooks.slack.com.evil.example/services/T0/B0/xyz", False),
        ("slack", "https://evil.example/hooks.slack.com/services/T0", False),
        ("slack", "https://hooks.slack.com@evil.example/services/T0", False),
        ("slack", "http://hooks.slack.com/services/T0", False),
        ("slack", "https://slack.com/services/T0", False),
        ("discord", "https://discord.com/api/webhooks/1/abc", True),
        ("discord", "https://discordapp.com/api/webhooks/1/abc", True),
        ("discord", "https://discord.com/api/webhooks/1/abc/slack", True),
        ("discord", "https://discord.com/other", False),
        ("discord", "https://discord.com.evil.example/api/webhooks/1/abc", False),
        ("discord", "https://cdn.discord.com/api/webhooks/1/abc", False),
        ("legacy_list", "https://anything.example.org/x", True),
        ("envelope", "https://anything.example.org/x", True),
    ],
)
def test_chat_formats_only_go_to_their_own_hosts(format_, url, allowed):
    if allowed:
        guard.check_chat_destination(format_, url)
    else:
        with pytest.raises(guard.DestinationRefused) as refused:
            guard.check_chat_destination(format_, url)
        assert refused.value.code == "host_not_allowed"
