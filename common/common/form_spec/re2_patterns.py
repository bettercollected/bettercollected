"""Answer patterns, the way the server reads them: with RE2.

The server matches every answer pattern with RE2 (``google-re2``, linear
time: backend ``services/answer_validation.py``). A pattern RE2 cannot
compile is never checked, so it is refused when it is saved instead (see
``form_spec.models.checked_pattern``): RE2 has no lookarounds and no
backreferences. The respondent's browser does not run creator-written
patterns at all; it only checks the built-in format presets.

``re2`` is imported on first use: the backend has it, the other services that
share this package do not need it. Without it a pattern is checked with
Python's ``re`` instead, which is only a stand-in (the backend is the one that
saves forms).
"""

import re
from typing import Any, Optional

# RE2 memory per pattern: heavy patterns (``^\p{L}{0,300}$``) fail to compile
# within it in a few milliseconds instead of taking 100+ ms; every preset
# compiles in well under a millisecond.
PATTERN_MAX_MEM = 1 << 20
# Matching costs up to (text length x program size) when RE2 falls back from
# its DFA: a bigger program is not used.
PATTERN_MAX_PROGRAM = 5_000

# JavaScript's \s: Unicode spaces (ASCII only in RE2).
JS_SPACE_CLASS = (
    r"\s\x{a0}\x{1680}\x{2000}-\x{200a}\x{2028}\x{2029}\x{202f}\x{205f}"
    r"\x{3000}\x{feff}"
)


def to_re2_syntax(pattern: str) -> str:
    """Rewrite the JavaScript-only bits of a pattern RE2 reads differently:
    ``\\uXXXX`` / ``\\u{...}`` escapes, and ``\\s`` (Unicode spaces in
    JavaScript, ASCII in RE2). Everything else is passed on as written."""
    out = []
    in_class = False
    i = 0
    while i < len(pattern):
        char = pattern[i]
        if char == "\\" and i + 1 < len(pattern):
            escaped = pattern[i + 1]
            if escaped == "u":
                if pattern.startswith("{", i + 2) and "}" in pattern[i + 3 :]:
                    end = pattern.index("}", i + 3)
                    out.append(r"\x{" + pattern[i + 3 : end] + "}")
                    i = end + 1
                    continue
                code = pattern[i + 2 : i + 6]
                if len(code) == 4 and all(c in "0123456789abcdefABCDEF" for c in code):
                    out.append(r"\x{" + code + "}")
                    i += 6
                    continue
            if escaped == "s":
                out.append(JS_SPACE_CLASS if in_class else f"[{JS_SPACE_CLASS}]")
            elif escaped == "S" and not in_class:
                out.append(f"[^{JS_SPACE_CLASS}]")
            else:
                out.append(pattern[i : i + 2])
            i += 2
            continue
        if char == "[" and not in_class:
            in_class = True
        elif char == "]" and in_class:
            in_class = False
        out.append(char)
        i += 1
    return "".join(out)


def re2_options() -> Any:
    import re2

    options = re2.Options()
    # RE2 would print the pattern to stderr when it does not compile.
    options.log_errors = False
    options.never_capture = True
    options.max_mem = PATTERN_MAX_MEM
    return options


_options: Any = None


def re2_problem(pattern: str) -> Optional[str]:
    """Why RE2 cannot use ``pattern`` (its own words), or None when it can:
    it compiles within PATTERN_MAX_MEM and its program stays within
    PATTERN_MAX_PROGRAM. Cheap and bounded: RE2 compiles in time and memory
    linear in the pattern's size, and refuses what would be too big."""
    global _options
    try:
        import re2
    except ImportError:  # a service without RE2 is not the one saving forms
        try:
            re.compile(pattern)
        except re.error as error:
            return str(error)
        return None
    if _options is None:
        _options = re2_options()
    try:
        compiled = re2.compile(to_re2_syntax(pattern).encode("utf-8"), _options)
    except Exception as error:  # re2.error and its subclasses
        detail = error.args[0] if error.args else error
        if isinstance(detail, bytes):
            detail = detail.decode("utf-8", "replace")
        return str(detail)
    if compiled.programsize > PATTERN_MAX_PROGRAM:
        return "the pattern is too large"
    return None
