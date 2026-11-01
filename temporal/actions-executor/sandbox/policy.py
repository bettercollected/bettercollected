"""What action code may say. The first of the sandbox's layers, and the least
trusted one: the code is parsed and refused when it names something that has
ever been a way out of a restricted ``exec``.

This is **not** the security boundary. The boundary is the process the code
runs in (``confine.py``: no file, no socket, no ``execve``, no secret, limits)
and the broker that performs every effect (``broker.py``). The checks here only
turn the usual tricks into a clear refusal before anything runs, and make the
next layer something an attacker has to find a hole in as well.

Refused: ``import``, classes, ``async``/``await``/``yield``, any attribute that
starts with an underscore and any name that starts with two (``__class__``,
``__globals__``, ``__subclasses__``, ``__import__`` ...), attributes of frames, generators, coroutines,
tracebacks and code objects (``f_globals``, ``gi_frame``, ``tb_frame``,
``co_code`` ...), ``str.format`` and ``format_map`` (a format string reads
attributes without naming them), and the builtins that reach outside
(``eval``, ``exec``, ``compile``, ``open``, ``getattr`` ...).
"""

import ast
from typing import Optional

MAX_SOURCE_BYTES = 64 * 1024
MAX_NODES = 20_000

FORBIDDEN_NODES = (
    ast.Import,
    ast.ImportFrom,
    ast.ClassDef,
    ast.AsyncFunctionDef,
    ast.AsyncFor,
    ast.AsyncWith,
    ast.Await,
    ast.Yield,
    ast.YieldFrom,
)

FORBIDDEN_ATTRIBUTES = frozenset(
    {"format", "format_map", "mro", "gi_frame", "gi_code", "cr_frame", "cr_code"}
)
FORBIDDEN_ATTRIBUTE_PREFIXES = ("_", "gi_", "cr_", "ag_", "f_", "tb_", "co_")

FORBIDDEN_NAMES = frozenset(
    {
        "eval",
        "exec",
        "compile",
        "open",
        "getattr",
        "setattr",
        "delattr",
        "hasattr",
        "globals",
        "locals",
        "vars",
        "dir",
        "type",
        "object",
        "super",
        "breakpoint",
        "input",
        "memoryview",
        "property",
        "staticmethod",
        "classmethod",
        "help",
        "exit",
        "quit",
    }
)


class PolicyViolation(Exception):
    """The code names something it may not. ``str()`` says what and where."""


def _where(node: ast.AST) -> str:
    line = getattr(node, "lineno", None)
    return f" (line {line})" if line else ""


def check_source(source: Optional[str]) -> ast.Module:
    """The parsed code, or :class:`PolicyViolation`."""
    source = source or ""
    if not isinstance(source, str):
        raise PolicyViolation("the action code is not text")
    if len(source.encode("utf-8", "replace")) > MAX_SOURCE_BYTES:
        raise PolicyViolation("the action code is too long")
    try:
        tree = ast.parse(source, filename="<action>", mode="exec")
    except (SyntaxError, ValueError, RecursionError, MemoryError) as error:
        raise PolicyViolation(
            f"the action code does not parse: {type(error).__name__}"
        ) from None
    count = 0
    for node in ast.walk(tree):
        count += 1
        if count > MAX_NODES:
            raise PolicyViolation("the action code is too large")
        if isinstance(node, FORBIDDEN_NODES):
            raise PolicyViolation(
                f"{type(node).__name__} is not allowed in action code{_where(node)}"
            )
        if isinstance(node, ast.Attribute):
            attr = node.attr
            if attr in FORBIDDEN_ATTRIBUTES or attr.startswith(
                FORBIDDEN_ATTRIBUTE_PREFIXES
            ):
                raise PolicyViolation(
                    f"the attribute .{attr} is not allowed in action code{_where(node)}"
                )
        elif isinstance(node, ast.Name):
            if node.id in FORBIDDEN_NAMES or node.id.startswith("__"):
                raise PolicyViolation(
                    f"the name {node.id} is not allowed in action code{_where(node)}"
                )
        elif isinstance(node, (ast.FunctionDef, ast.Lambda)):
            _check_arguments(node)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            if node.name.startswith("__"):
                raise PolicyViolation(f"the name {node.name} is not allowed")
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            for name in node.names:
                if name.startswith("__"):
                    raise PolicyViolation(f"the name {name} is not allowed")
    return tree


def _check_arguments(node) -> None:
    arguments = node.args
    every = [
        *arguments.posonlyargs,
        *arguments.args,
        *arguments.kwonlyargs,
        *([arguments.vararg] if arguments.vararg else []),
        *([arguments.kwarg] if arguments.kwarg else []),
    ]
    for argument in every:
        if argument.arg.startswith("__") or argument.arg in FORBIDDEN_NAMES:
            raise PolicyViolation(f"the name {argument.arg} is not allowed")
    if isinstance(node, ast.FunctionDef) and node.name.startswith("__"):
        raise PolicyViolation(f"the name {node.name} is not allowed")
