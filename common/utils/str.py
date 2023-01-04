import re
from http import HTTPStatus

from starlette.exceptions import HTTPException


def is_camel_case(string: str) -> bool:
    """Checks if the string is in camel case."""
    return bool(re.match(r"^[a-z]+([A-Z][a-z]*)*$", string))


def is_snake_case(string: str) -> bool:
    """Checks if the string is in snake case."""
    return bool(re.match(r"^[a-z_][0-9a-z_]*$", string))


def is_pascal_case(string: str) -> bool:
    """Checks if the string is in pascal case."""
    return bool(re.match(r"^([A-Z][a-z]*)+$", string))


def to_camelcase(string: str) -> str:
    """Converts snake_case --> camelCase"""
    # TODO: Split using regex (with also space)

    if is_camel_case(string):
        return string
    if is_pascal_case(string) and not string.isupper():
        return string[0].lower() + string[1:]
    words = re.sub(r"[^A-Za-z0-9]+", "_", string).split("_")
    return "".join(
        [word.capitalize() if i > 0 else word.lower() for i, word in enumerate(words)]
    )


def to_snakecase(string: str) -> str:
    """Converts string --> snake_case"""
    if is_snake_case(string):
        return string
    if string.isupper():
        return string.lower()
    if is_camel_case(string) or is_pascal_case(string):
        # Put "_" before each capitalized letter (if not preceded with one like "TML" in "HTML")
        string = re.sub(r"(?!^)([A-Z]+)", r"_\1", string)
    else:
        string = re.sub(r"[^A-Za-z0-9]+", "_", string)
    return string.lower()


def get_valid_email(email: str) -> str:
    regex = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
    if not re.search(regex, email):
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST, detail="Must be a valid email address."
        )
    return email.lower()
