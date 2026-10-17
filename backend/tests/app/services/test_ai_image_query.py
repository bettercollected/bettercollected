"""AI image search looks for the form's subject, never its look.

New forms start with the Leaflet theme, so a query built from the theme name
would search Unsplash for "Leaflet ...". The prompts ask for subject-only
queries and the tool executor drops any theme or style name the model still
puts at either end of the query.
"""

import json
from types import SimpleNamespace

import pytest

from backend.app.constants.themes import THEME_STYLES, theme_dict
from backend.app.services import google_ai_provider, openai_provider
from backend.app.services.ai_form_tools import (
    TOOL_DEFINITIONS,
    execute_tool,
    image_query,
)
from backend.app.services.openai_provider import OpenAIFormProvider


class FakeUnsplash:
    def __init__(self):
        self.queries = []

    async def search_photos(self, query, per_page=5, orientation="landscape"):
        self.queries.append(query)
        return [{"url": f"https://images.example/{len(self.queries)}.jpg"}]


def _tool_call(call_id, name, args):
    return SimpleNamespace(
        id=call_id,
        function=SimpleNamespace(name=name, arguments=json.dumps(args)),
    )


def _reply(tool_calls=None, content=None):
    message = SimpleNamespace(tool_calls=tool_calls, content=content)
    finish = "tool_calls" if tool_calls else "stop"
    return SimpleNamespace(
        choices=[SimpleNamespace(finish_reason=finish, message=message)]
    )


class FakeCompletions:
    def __init__(self, replies):
        self._replies = list(replies)

    async def create(self, **kwargs):
        return self._replies.pop(0)


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("Leaflet community centre visit", "community centre visit"),
        ("community centre visit leaflet style", "community centre visit"),
        ("purple minimal healthcare", "minimal healthcare"),
        ("Default theme customer feedback", "customer feedback"),
        ("Red Cross blood donation", "Cross blood donation"),
        ("volunteer Red Cross drive", "volunteer Red Cross drive"),
        ("Leaflet", ""),
        ("", ""),
    ],
)
def test_image_query_drops_theme_and_style_names_at_the_ends(raw, expected):
    assert image_query(raw) == expected


@pytest.mark.parametrize("name", [*theme_dict, *THEME_STYLES])
async def test_every_theme_and_style_name_is_kept_out_of_the_query(name):
    unsplash = FakeUnsplash()
    await execute_tool(
        "search_images", {"query": f"{name} school trip consent"}, unsplash
    )
    assert unsplash.queries == ["school trip consent"]


async def test_a_query_of_only_look_words_searches_nothing():
    unsplash = FakeUnsplash()
    result = await execute_tool("search_images", {"query": "Leaflet theme"}, unsplash)
    assert result == []
    assert unsplash.queries == []


async def test_leaflet_ai_form_image_queries_follow_the_topic():
    """A Leaflet form made by the AI: every image search is about the visit."""
    unsplash = FakeUnsplash()
    provider = OpenAIFormProvider(unsplash)
    final = {
        "title": "Community centre visit",
        "theme_name": "Leaflet",
        "welcome_image_url": "https://images.example/1.jpg",
        "fields": [],
    }
    provider._client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=FakeCompletions(
                [
                    _reply([_tool_call("t1", "get_available_themes", {})]),
                    _reply(
                        [
                            _tool_call(
                                "i1",
                                "search_images",
                                {"query": "Leaflet community centre visit"},
                            ),
                            _tool_call(
                                "i2",
                                "search_images",
                                {"query": "community centre activities leaflet"},
                            ),
                        ]
                    ),
                    _reply(content=json.dumps(final)),
                ]
            )
        )
    )

    form = await provider.generate_form("A form about a visit to the community centre")

    assert form["theme_name"] == "Leaflet"
    assert len(unsplash.queries) == 2
    for query in unsplash.queries:
        assert "leaflet" not in query.lower()
        assert "community centre" in query


def test_prompts_and_tool_ask_for_subject_only_queries():
    search = next(t for t in TOOL_DEFINITIONS if t["name"] == "search_images")
    texts = [
        openai_provider.SYSTEM_PROMPT,
        google_ai_provider.SYSTEM_PROMPT,
        search["description"],
        search["parameters"]["properties"]["query"]["description"],
    ]
    for text in texts:
        assert "{theme_name}" not in text
        assert "combining the chosen theme" not in text
        assert "combines the chosen theme" not in text
