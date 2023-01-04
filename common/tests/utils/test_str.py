import pytest

from utils.str import (
    is_camel_case,
    is_pascal_case,
    is_snake_case,
    to_camelcase,
    to_snakecase,
)


@pytest.mark.parametrize(
    "test_input, expected",
    [
        ("isCamelCase", True),
        ("IsCamelCase", False),
        ("is_camel_case", False),
        ("is_Camel_Case", False),
    ],
)
def test_is_camel_case(test_input, expected):
    assert is_camel_case(test_input) is expected


@pytest.mark.parametrize(
    "test_input, expected",
    [
        ("is_snake_case", True),
        ("IsSnakeCase", False),
        ("isSnakeCase", False),
        ("is_Snake_Case", False),
    ],
)
def test_is_snake_case(test_input, expected):
    assert is_snake_case(test_input) is expected


@pytest.mark.parametrize(
    "test_input, expected",
    [
        ("IsPascalCase", True),
        ("isPascalCase", False),
        ("is_pascal_case", False),
        ("is_Pascal_Case", False),
    ],
)
def test_is_pascal_case(test_input, expected):
    assert is_pascal_case(test_input) is expected


@pytest.mark.parametrize(
    "test_input, expected",
    [
        ("ToCamelCase", "toCamelCase"),
        ("to_camel_case", "toCamelCase"),
        ("to_Camel_Case", "toCamelCase"),
    ],
)
def test_to_camelcase(test_input, expected):
    assert to_camelcase(test_input) == expected


@pytest.mark.parametrize(
    "test_input, expected",
    [
        ("ToSnakeCase", "to_snake_case"),
        ("to_snake_case", "to_snake_case"),
        ("to_Snake_Case", "to_snake_case"),
    ],
)
def test_to_snakecase(test_input, expected):
    assert to_snakecase(test_input) == expected
