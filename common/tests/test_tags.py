"""What a tag may be (common/tags.py; twin of webapp/src/utils/tags.ts)."""

import pytest

from common.tags import TAG_LENGTH_MAX, TAGS_MAX, duplicate_index, is_tag, tag_key


def test_the_caps():
    assert (TAGS_MAX, TAG_LENGTH_MAX) == (30, 40)


@pytest.mark.parametrize("tag", ["vegan", "gluten free", "café au lait", "日本語", "שלום", "a", "x-y_z.1", "a\u3000b"])
def test_a_tag(tag):
    assert is_tag(tag)


@pytest.mark.parametrize(
    "tag",
    ["", " a", "a ", "a\u3000", "\u3000a", "a,b", "a;b", "a\tb", "a\nb", "a\x07b", "a\x85b", "a\u2028b", "a\u2029b", 5, None],
)
def test_not_a_tag(tag):
    assert not is_tag(tag)


@pytest.mark.parametrize(
    "character",
    [
        "\u061c",
        "\u200b",
        "\u200c",
        "\u200d",
        "\u200e",
        "\u200f",
        "\u202a",
        "\u202b",
        "\u202c",
        "\u202d",
        "\u202e",
        "\u2066",
        "\u2067",
        "\u2068",
        "\u2069",
        "\ufeff",
        "\u00ad",
    ],
)
def test_bidirectional_and_zero_width_format_characters_are_refused(character):
    """They reverse or hide text in a view and defeat the comparison of tags."""
    assert not is_tag(f"re{character}d")
    assert not is_tag(character)
    assert not is_tag(f"{character}red")


def test_tags_are_compared_in_lower_case():
    assert tag_key("Red") == "red"
    assert duplicate_index(["a", "B", "b"]) == 2
    assert duplicate_index(["a", "b"]) is None
