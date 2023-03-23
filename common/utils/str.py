import re
from http import HTTPStatus

from starlette.exceptions import HTTPException


def is_camel_case(string: str) -> bool:
    """
    Returns True if the given string is in camel case, False otherwise.

    Camel case is defined as a naming convention where the first letter of each word is capitalized,
    except for the first word, which is in lowercase.

    Args:
        string (str): The string to check.

    Returns:
        bool: True if the given string is in camel case, False otherwise.
    """
    return bool(re.match(r"^[a-z]+([A-Z][a-z]*)*$", string))


def is_snake_case(string: str) -> bool:
    """
    Returns True if the given string is in snake case, False otherwise.

    Snake case is defined as a naming convention where words are separated by an underscore,
    and all letters are in lowercase.

    Args:
        string (str): The string to check.

    Returns:
        bool: True if the given string is in snake case, False otherwise.
    """
    return bool(re.match(r"^[a-z_][0-9a-z_]*$", string))


def is_pascal_case(string: str) -> bool:
    """
    Returns True if the given string is in pascal case, False otherwise.

    Pascal case is defined as a naming convention where each word in a compound word is capitalized,
    with no spaces or underscores between words.

    Args:
        string (str): The string to check.

    Returns:
        bool: True if the given string is in pascal case, False otherwise.
    """
    return bool(re.match(r"^([A-Z][a-z]*)+$", string))


def to_camelcase(string: str) -> str:
    """
    Converts the given snake_case string to camelCase.

    Args:
        string (str): The snake_case string to convert.

    Returns:
        str: The given string in camelCase.
    """
    if is_camel_case(string):
        return string
    if is_pascal_case(string) and not string.isupper():
        return string[0].lower() + string[1:]
    words = re.sub(r"[^A-Za-z0-9]+", "_", string).split("_")
    return "".join(
        [word.capitalize() if i > 0 else word.lower() for i, word in enumerate(words)]
    )


def to_snakecase(string: str) -> str:
    """
    Converts the given string to snake_case.

    Args:
        string (str): The string to convert.

    Returns:
        str: The given string in snake_case.
    """
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
    """
    Returns a lowercase version of the given email if it is a valid email address.
    Otherwise, raises an HTTPException with a BAD_REQUEST status code.

    Args:
        email (str): The email address to validate.

    Returns:
        str: The lowercase version of the given email address.

    Raises:
        HTTPException: If the given email address is not a valid email.
    """
    regex = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
    if not re.search(regex, email):
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST, detail="Must be a valid email address."
        )
    return email.lower()
