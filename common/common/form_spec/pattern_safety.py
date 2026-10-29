"""Answer patterns that could freeze a browser (ReDoS).

The server matches answer patterns with RE2 (linear time), but the
respondent's browser evaluates them with JavaScript's backtracking
``RegExp``: a pattern such as ``^(a+)+$`` is valid for both and takes
exponential time in the browser on an answer like ``aaaa...b``. This module
finds the pattern shapes whose backtracking cost can explode, by a small
structural analysis of the parsed pattern (never a regex on a regex), so
that the builder, the API and the importer refuse them when they are saved
and the respondent form never hands them to ``RegExp``.

``pattern_hazard(pattern)`` returns None for a pattern that is fine, or one
of the codes below. The webapp twin is ``webapp/src/utils/pattern-safety.ts``
(same algorithm); the shared table of cases is
``docs/spec/pattern-safety.cases.json``, run by both sides.

Hazards (conservative: a pattern that is merely unusual may be refused,
never one of these shapes accepted):

- ``backreference``: ``\\1``, ``\\k<name>``, ``(?P=name)``. Matching them
  needs backtracking even for simple patterns (RE2 refuses them too).
- ``nested_repeat``: a repeated part (``x?`` too) inside a repeated group
  that can start with what may follow it, so one text splits into
  iterations in many ways: ``(a+)+``, ``(a*)*``, ``(\\w+\\s?)+``, ``((ab)+)+``,
  ``(a?a){30}``. ``(\\w+\\s)+`` is fine: the separator ends every iteration.
- ``overlapping_alternatives``: a repeated group with two alternatives that
  can start with the same character: ``(a|aa)+``, ``(\\w|\\d){9}``.
- ``empty_repeat``: a repeat (bounded or not) of something that can match
  nothing: ``(\\s*)+`` and ``(a?|b?){28}``.
- ``adjacent_repeats``: repeats in one sequence that match the same
  characters multiply their work: ``.*a.*a.*a``, ``\\d*\\d*\\d*``, ``a?`` twenty
  times in a row, ``(a|aa)`` twenty times in a row. Each variable repeat
  counts as its number of ways to match (an unbounded one as
  ``WORK_UNBOUNDED``), the ones that overlap (also across a mandatory
  character they can match themselves, and from inside optional groups and
  alternations: ``a*(?:b|a*)(?:c|a*)x``) multiply, and the product may not
  pass ``WORK_LIMIT``: at most two unbounded repeats. A pattern that does not
  start with ``^`` is tried at every start of the answer, so it gets
  ``WORK_LIMIT / WORK_UNBOUNDED``: ``a{1,99}a{1,99}a{1,99}!`` and
  ``\\d*\\d*x`` need a ``^``, with it they are fine.
- ``inline_flags``: ``(?i)``, ``(?i:...)`` and the like change what
  characters match; the analysis works on exact sets, so they are refused.
- ``too_complex``: longer than ``PATTERN_MAX_LENGTH`` or nested deeper than
  ``MAX_DEPTH``.
- ``unparseable``: not a pattern this analysis can read (a broken one, or a
  syntax it does not know); a pattern that cannot be analysed is not trusted.
  Callers that only store patterns skip a broken one no engine would run
  (``services/form_patterns.py``).

Two overlapping unbounded repeats (``\\d*\\.?\\d*``) cost quadratic time at
most and are allowed, as are lookarounds (their content is analysed on its
own). The check reduces the risk, it cannot prove that no pattern is
super-linear; the respondent form also tests only short answers
(``PATTERN_TEST_MAX_LENGTH``), which bounds what is left.
Character sets are exact for classes, ranges and the escapes ``\\d \\w \\s``;
Unicode properties (``\\p{L}``) are approximated by a superset (ASCII letters
or digits plus everything above U+007F, or everything), which can only add
overlaps, never hide one.
"""

from typing import Dict, List, Optional, Tuple

PATTERN_MAX_LENGTH = 200
MAX_DEPTH = 40
# Work estimate per start position: an unbounded repeat counts as this many
# ways to match (about the longest text the browser tests, PATTERN_TEST_MAX_
# LENGTH in the webapp's answer-rules.ts), and the repeats of one sequence
# that overlap may multiply to at most WORK_LIMIT.
WORK_UNBOUNDED = 1000
WORK_LIMIT = 1_000_000

BACKREFERENCE = "backreference"
NESTED_REPEAT = "nested_repeat"
OVERLAPPING_ALTERNATIVES = "overlapping_alternatives"
EMPTY_REPEAT = "empty_repeat"
ADJACENT_REPEATS = "adjacent_repeats"
TOO_COMPLEX = "too_complex"
UNPARSEABLE = "unparseable"
INLINE_FLAGS = "inline_flags"

HAZARDS = (
    BACKREFERENCE,
    NESTED_REPEAT,
    OVERLAPPING_ALTERNATIVES,
    EMPTY_REPEAT,
    ADJACENT_REPEATS,
    TOO_COMPLEX,
    UNPARSEABLE,
    INLINE_FLAGS,
)

# Shown to editors; the webapp has the same texts (twin, plus Dutch).
HAZARD_MESSAGES: Dict[str, str] = {
    BACKREFERENCE: "A pattern cannot refer back to an earlier group (\\1): it "
    "can take a browser very long to check.",
    NESTED_REPEAT: "A repeated group inside a repeated group, such as (a+)+, "
    "can take a browser very long to check. Make each repeat end in a "
    "separator or use one repeat.",
    OVERLAPPING_ALTERNATIVES: "A repeated group whose choices can start with "
    "the same character, such as (a|aa)+, can take a browser very long to "
    "check. Make the choices start differently or merge them.",
    EMPTY_REPEAT: "A repeated group that can match nothing, such as (a?)*, can "
    "take a browser very long to check.",
    ADJACENT_REPEATS: "Several repeats in a row that match the same characters, "
    "such as \\d*\\d*\\d*, can take a browser very long to check. Use fewer, "
    "or start the pattern with ^.",
    TOO_COMPLEX: "This pattern is too long or too complex to check safely. "
    "Shorten or simplify it.",
    UNPARSEABLE: "This pattern could not be read to check it safely. " "Simplify it.",
    INLINE_FLAGS: "Flags written inside a pattern, such as (?i), are not "
    "supported. Match both cases with a class such as [Aa] instead.",
}

MAX_CODEPOINT = 0x10FFFF
_ASCII_LETTERS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
Ranges = Tuple[Tuple[int, int], ...]
ALL: Ranges = ((0, MAX_CODEPOINT),)
_LINE_TERMINATORS: Ranges = ((10, 10), (13, 13), (0x2028, 0x2029))
_DIGITS: Ranges = ((48, 57),)
_WORD: Ranges = ((48, 57), (65, 90), (95, 95), (97, 122))
_SPACE: Ranges = (
    (9, 13),
    (32, 32),
    (0xA0, 0xA0),
    (0x1680, 0x1680),
    (0x2000, 0x200A),
    (0x2028, 0x2029),
    (0x202F, 0x202F),
    (0x205F, 0x205F),
    (0x3000, 0x3000),
    (0xFEFF, 0xFEFF),
)
_LETTERS_SUPERSET: Ranges = ((65, 90), (97, 122), (0x80, MAX_CODEPOINT))
_NUMBERS_SUPERSET: Ranges = ((48, 57), (0x80, MAX_CODEPOINT))


class _Unparseable(Exception):
    pass


class _TooDeep(Exception):
    pass


class _InlineFlags(Exception):
    pass


def _norm(ranges: List[Tuple[int, int]]) -> Ranges:
    merged: List[Tuple[int, int]] = []
    for low, high in sorted(ranges):
        if merged and low <= merged[-1][1] + 1:
            if high > merged[-1][1]:
                merged[-1] = (merged[-1][0], high)
        else:
            merged.append((low, high))
    return tuple(merged)


def _negate(ranges: Ranges) -> Ranges:
    out: List[Tuple[int, int]] = []
    start = 0
    for low, high in ranges:
        if low > start:
            out.append((start, low - 1))
        start = high + 1
    if start <= MAX_CODEPOINT:
        out.append((start, MAX_CODEPOINT))
    return tuple(out)


def _union(a: Ranges, b: Ranges) -> Ranges:
    if not a:
        return b
    if not b:
        return a
    return _norm(list(a) + list(b))


def _overlap(a: Ranges, b: Ranges) -> bool:
    i = j = 0
    while i < len(a) and j < len(b):
        if a[i][1] < b[j][0]:
            i += 1
        elif b[j][1] < a[i][0]:
            j += 1
        else:
            return True
    return False


def _property(name: str, negated: bool) -> Ranges:
    key = name.split("=")[-1].strip()
    if negated:
        return ALL
    if key[:1] == "L":
        return _LETTERS_SUPERSET
    if key[:1] == "N":
        return _NUMBERS_SUPERSET
    return ALL


# ---------------------------------------------------------------- the tree
# A node is a tuple: ("char", ranges) ("zero",) ("bol",) ("seq", [nodes])
# ("alt", [nodes]) ("rep", body, min, max-or-None) ("look", body)
# ("backref",)


class _Parser:
    def __init__(self, pattern: str):
        self.p = pattern
        self.i = 0
        self.depth = 0
        self.backref = False

    def eof(self) -> bool:
        return self.i >= len(self.p)

    def peek(self, offset: int = 0) -> str:
        j = self.i + offset
        return self.p[j] if j < len(self.p) else ""

    def parse(self):
        node = self.alternation()
        if not self.eof():
            raise _Unparseable()  # a stray ")"
        return node

    def alternation(self):
        self.depth += 1
        if self.depth > MAX_DEPTH:
            raise _TooDeep()
        branches = [self.sequence()]
        while self.peek() == "|":
            self.i += 1
            branches.append(self.sequence())
        self.depth -= 1
        return branches[0] if len(branches) == 1 else ("alt", branches)

    def sequence(self):
        items: list = []
        while not self.eof() and self.peek() not in ("|", ")"):
            atom = self.atom()
            atom = self.quantified(atom)
            if atom[0] == "seq":
                items.extend(atom[1])  # a group without a repeat is just its content
            else:
                items.append(atom)
        if len(items) == 1:
            return items[0]
        return ("seq", items)

    def quantified(self, atom):
        char = self.peek()
        low = high = None
        if char == "*":
            low, high = 0, None
            self.i += 1
        elif char == "+":
            low, high = 1, None
            self.i += 1
        elif char == "?":
            low, high = 0, 1
            self.i += 1
        elif char == "{":
            found = self.braces()
            if found is None:
                return atom
            low, high = found
        else:
            return atom
        # lazy or possessive suffix
        if self.peek() in ("?", "+"):
            self.i += 1
        if atom[0] in ("zero", "bol"):
            return atom  # a repeated anchor or lookaround matches nothing more
        if atom[0] == "look":
            return atom
        return ("rep", atom, low, high)

    def braces(self):
        """{n} {n,} {n,m} at the cursor, consumed; None (and nothing consumed)
        when it is not a quantifier, which then reads as literal text."""
        j = self.i + 1
        text = self.p
        start = j
        while j < len(text) and text[j].isdigit() and text[j].isascii():
            j += 1
        if j == start:
            return None
        low = int(text[start:j])
        high: Optional[int] = low
        if j < len(text) and text[j] == ",":
            j += 1
            start = j
            while j < len(text) and text[j].isdigit() and text[j].isascii():
                j += 1
            high = int(text[start:j]) if j > start else None
        if j >= len(text) or text[j] != "}":
            return None
        self.i = j + 1
        return low, high

    def atom(self):
        char = self.peek()
        if char == "(":
            return self.group()
        if char == "[":
            return ("char", self.char_class())
        if char == ".":
            self.i += 1
            return ("char", _negate(_LINE_TERMINATORS))
        if char == "^":
            self.i += 1
            return ("bol",)
        if char == "$":
            self.i += 1
            return ("zero",)
        if char == "\\":
            return self.escape()
        if char in ("*", "+", "?"):
            raise _Unparseable()  # nothing to repeat
        self.i += 1
        return ("char", self.literal(char))

    @staticmethod
    def literal(char: str) -> Ranges:
        code = ord(char)
        return ((code, code),)

    def group(self):
        self.i += 1  # (
        kind = "group"
        if self.peek() == "?":
            rest = self.p[self.i + 1 : self.i + 4]
            if rest.startswith(("=", "!")):
                kind = "look"
                self.i += 2
            elif rest.startswith(("<=", "<!")):
                kind = "look"
                self.i += 3
            elif rest.startswith("#"):
                end = self.p.find(")", self.i)
                if end < 0:
                    raise _Unparseable()
                self.i = end + 1
                return ("zero",)
            elif rest.startswith("P="):
                end = self.p.find(")", self.i)
                if end < 0:
                    raise _Unparseable()
                self.i = end + 1
                self.backref = True
                return ("backref",)
            elif rest.startswith("P<") or (
                rest.startswith("<") and not rest.startswith(("<=", "<!"))
            ):
                end = self.p.find(">", self.i)
                if end < 0:
                    raise _Unparseable()
                self.i = end + 1
            elif rest.startswith(":") or rest.startswith(">"):
                self.i += 2
            else:
                # inline flags: (?i) is a flag-only group, (?i:...) scopes them
                j = self.i + 1
                while j < len(self.p) and (
                    self.p[j] in _ASCII_LETTERS or self.p[j] == "-"
                ):
                    j += 1
                if j >= len(self.p) or j == self.i + 1:
                    raise _Unparseable()
                if self.p[j] not in (")", ":"):
                    raise _Unparseable()
                # (?i) and (?i:...) change what characters match; the
                # analysis works on exact sets, so they are refused
                raise _InlineFlags()
        body = self.alternation()
        if self.peek() != ")":
            raise _Unparseable()
        self.i += 1
        if kind == "look":
            return ("look", body)
        return body

    def escape(self):
        self.i += 1  # backslash
        if self.eof():
            raise _Unparseable()
        char = self.peek()
        self.i += 1
        if char == "A":
            return ("bol",)
        if char in "bBZzG":
            return ("zero",)
        if char in "123456789":
            self.backref = True
            return ("backref",)
        if char == "k" and self.peek() == "<":
            self.backref = True
            end = self.p.find(">", self.i)
            self.i = end + 1 if end >= 0 else len(self.p)
            return ("backref",)
        return ("char", self.class_escape(char))

    def class_escape(self, char: str) -> Ranges:
        """The set an escape stands for (after the backslash and its letter,
        both consumed); a lone escaped character stands for itself."""
        if char == "d":
            return _DIGITS
        if char == "D":
            return _negate(_DIGITS)
        if char == "w":
            return _WORD
        if char == "W":
            return _negate(_WORD)
        if char == "s":
            return _SPACE
        if char == "S":
            return _negate(_SPACE)
        if char in ("p", "P"):
            if self.peek() == "{":
                end = self.p.find("}", self.i)
                if end < 0:
                    raise _Unparseable()
                name = self.p[self.i + 1 : end]
                self.i = end + 1
            else:
                name = self.p[self.i : self.i + 1]
                self.i += 1
            return _property(name, char == "P")
        if char == "x":
            return self._hex(2)
        if char == "u":
            if self.peek() == "{":
                end = self.p.find("}", self.i)
                if end < 0:
                    raise _Unparseable()
                digits = self.p[self.i + 1 : end]
                self.i = end + 1
                return self._code(digits)
            return self._hex(4)
        if char == "c":
            self.i += 1
            return ALL  # control character: not worth modelling
        mapped = {"n": 10, "r": 13, "t": 9, "f": 12, "v": 11, "0": 0}.get(char)
        if mapped is not None:
            return ((mapped, mapped),)
        return self.literal(char)

    def _hex(self, count: int) -> Ranges:
        digits = self.p[self.i : self.i + count]
        self.i += len(digits)
        return self._code(digits)

    @staticmethod
    def _code(digits: str) -> Ranges:
        if not digits or any(c not in "0123456789abcdefABCDEF" for c in digits):
            return ALL
        code = int(digits, 16)
        if code > MAX_CODEPOINT:
            return ALL
        return ((code, code),)

    def char_class(self) -> Ranges:
        self.i += 1  # [
        negated = False
        if self.peek() == "^":
            negated = True
            self.i += 1
        ranges: List[Tuple[int, int]] = []
        first = True
        while True:
            if self.eof():
                raise _Unparseable()
            char = self.peek()
            if char == "]" and not first:
                self.i += 1
                break
            first = False
            low = self.class_atom(ranges)
            if low is None:
                continue
            # a range a-z
            if self.peek() == "-" and self.peek(1) not in ("]", ""):
                self.i += 1
                high = self.class_atom(ranges)
                if high is None:
                    ranges.append((low, low))
                    ranges.append((45, 45))
                    continue
                if high < low:
                    raise _Unparseable()
                ranges.append((low, high))
            else:
                ranges.append((low, low))
        result = _norm(ranges)
        return _negate(result) if negated else result

    def class_atom(self, ranges: List[Tuple[int, int]]) -> Optional[int]:
        """One class member: the code of a single character, or None after
        adding a whole set (``\\d``, ``\\p{L}``) to ``ranges``."""
        char = self.peek()
        self.i += 1
        if char != "\\":
            return ord(char)
        if self.eof():
            raise _Unparseable()
        escaped = self.peek()
        self.i += 1
        if escaped == "b":
            return 8
        if escaped in "dDwWsSpP":
            ranges.extend(self.class_escape(escaped))
            return None
        found = self.class_escape(escaped)
        if len(found) == 1 and found[0][0] == found[0][1]:
            return found[0][0]
        ranges.extend(found)
        return None


class _Analysis:
    def __init__(self):
        self.problem: Optional[str] = None
        # by node identity; the tree outlives the analysis, so ids are unique
        self._info: Dict[int, Tuple[bool, Ranges]] = {}
        self._alphabet: Dict[int, Ranges] = {}
        self._alt_weights: Dict[int, int] = {}
        self._ids = 0
        self.anchored = False

    def flag(self, code: str) -> None:
        if self.problem is None:
            self.problem = code

    def info(self, node: tuple) -> Tuple[bool, Ranges]:
        """(can match the empty string, characters it can start with)."""
        key = id(node)
        cached = self._info.get(key)
        if cached is not None:
            return cached
        kind = node[0]
        if kind == "char":
            result = (False, node[1])
        elif kind in ("zero", "bol", "look"):
            result = (True, ())
        elif kind == "backref":
            result = (True, ALL)
        elif kind == "seq":
            nullable, first = True, ()
            for item in node[1]:
                item_nullable, item_first = self.info(item)
                first = _union(first, item_first)
                if not item_nullable:
                    nullable = False
                    break
            result = (nullable, first)
        elif kind == "alt":
            nullable, first = False, ()
            for branch in node[1]:
                branch_nullable, branch_first = self.info(branch)
                nullable = nullable or branch_nullable
                first = _union(first, branch_first)
            result = (nullable, first)
        else:  # rep
            body_nullable, body_first = self.info(node[1])
            result = (body_nullable or node[2] == 0, body_first)
        self._info[key] = result
        return result

    def walk(self, node: tuple, follow: Ranges, in_loop: bool) -> None:
        if self.problem is not None:
            return
        kind = node[0]
        if kind == "backref":
            self.flag(BACKREFERENCE)
        elif kind == "look":
            self.walk(node[1], (), in_loop)
        elif kind == "seq":
            items = node[1]
            ahead = follow
            for item in reversed(items):
                self.walk(item, ahead, in_loop)
                item_nullable, item_first = self.info(item)
                ahead = _union(item_first, ahead) if item_nullable else item_first
            self._adjacent(items)
        elif kind == "alt":
            branches = node[1]
            for branch in branches:
                self.walk(branch, follow, in_loop)
            if in_loop:
                seen: Ranges = ()
                for branch in branches:
                    first = self.info(branch)[1]
                    if _overlap(seen, first):
                        self.flag(OVERLAPPING_ALTERNATIVES)
                        return
                    seen = _union(seen, first)
        elif kind == "rep":
            body, low, high = node[1], node[2], node[3]
            nullable, first = self.info(body)
            # a fixed count (x{4}) has one way to match; a variable one
            # (x?, x+, x{2,5}) that can start what a loop's next round or
            # exit starts with is ambiguous
            variable = high is None or high != low
            if in_loop and variable and _overlap(first, follow):
                self.flag(NESTED_REPEAT)
                return
            if high is not None and high <= 1:
                self.walk(body, follow, in_loop)  # x? : not a loop itself
                return
            self.walk(body, _union(first, follow), True)
            # any repeat of something that can match nothing, bounded or
            # not: (a?|b?){28} has as many ways to match as it has rounds
            if nullable and self.problem is None:
                self.flag(EMPTY_REPEAT)

    def alphabet(self, node: tuple) -> Ranges:
        """Every character the node can match, anywhere in it."""
        key = id(node)
        cached = self._alphabet.get(key)
        if cached is not None:
            return cached
        kind = node[0]
        if kind == "char":
            result = node[1]
        elif kind in ("zero", "bol", "look"):
            result = ()
        elif kind == "backref":
            result = ALL
        elif kind == "rep":
            result = self.alphabet(node[1])
        else:  # seq, alt
            result = ()
            for child in node[1]:
                result = _union(result, self.alphabet(child))
        self._alphabet[key] = result
        return result

    def _flatten(self, items: list, out: list) -> None:
        """The ways of matching the same text that a sequence holds, in
        order: ("atom", characters, ways, gates, id) for a variable repeat
        or an ambiguous alternation, wherever it sits (inside an optional
        group or a loop too), ("mand", characters) for a character that must
        be there, and ("cut", ids) where mandatory characters end repeats of
        an optional group. A variable repeat has (max - min + 1) ways, an
        unbounded one WORK_UNBOUNDED. ``gates``: see ``_optional``."""
        for item in items:
            kind = item[0]
            if kind == "seq":
                self._flatten(item[1], out)
            elif kind == "rep":
                body, low, high = item[1], item[2], item[3]
                inner: list = []
                self._flatten(body[1] if body[0] == "seq" else [body], inner)
                has_atoms = any(e[0] == "atom" for e in inner)
                if high is not None and high <= 1:
                    # x? or x{1}: what is inside counts, wherever it is
                    if low == 0:
                        inner = self._optional(inner)
                        if not any(e[0] == "atom" for e in inner):
                            inner.append(self._atom(self.alphabet(body), 2))
                    out.extend(inner)
                    continue
                ways = (
                    WORK_UNBOUNDED
                    if high is None
                    else min(high - low + 1, WORK_UNBOUNDED)
                )
                if has_atoms:
                    # a loop over variable repeats: they count, a few rounds
                    # of them (the loop's own ambiguity is nested_repeat's),
                    # and so do the rounds themselves
                    inner = self._optional(inner, wrap=True)
                    for _ in range(min(max(low, 1), 3)):
                        out.extend(inner)
                self._emit(item, ways, out)
            elif kind == "alt":
                self._emit(item, self._alt_weight(item), out)
            elif kind == "char":
                out.append(("mand", item[1]))

    def _atom(self, characters: Ranges, ways: int) -> tuple:
        self._ids += 1
        return ("atom", characters, ways, (), self._ids)

    @staticmethod
    def _optional(inner: list, wrap: bool = False) -> list:
        """The entries of an optional group as they go into the sequence
        around it. The group may be skipped, so its mandatory characters
        never end the repeats outside it; they end the repeats inside it (a
        ``cut``: those multiply with what came before the cut, not after),
        and keep the repeats after them from multiplying with outside
        repeats that cannot match them (``gates``). ``wrap``: the group is a
        loop, so its leading mandatory characters also follow its last
        repeats."""
        result: list = []
        live: Dict[int, Ranges] = {}  # repeats not ended yet: id -> characters
        gates: Ranges = ()
        leading: list = []  # mandatory characters before the first repeat

        def mandatory(characters: Ranges) -> None:
            if live and not any(_overlap(other, characters) for other in live.values()):
                result.append(("cut", frozenset(live)))
                live.clear()

        for entry in inner:
            if entry[0] == "atom":
                result.append(entry[:3] + (_union(entry[3], gates),) + entry[4:])
                live[entry[4]] = entry[1]
            elif entry[0] == "cut":
                result.append(entry)
                for gone in entry[1]:
                    live.pop(gone, None)
            else:
                if not live and not any(e[0] == "atom" for e in result):
                    leading.append(entry)
                gates = _union(gates, entry[1])
                mandatory(entry[1])
        if wrap:
            for entry in leading:
                mandatory(entry[1])
        return result

    def _emit(self, item: tuple, ways: int, out: list) -> None:
        if ways > 1:
            out.append(self._atom(self.alphabet(item), ways))
        elif not self.info(item)[0]:
            out.append(("mand", self.alphabet(item)))

    def _alt_weight(self, item: tuple) -> int:
        """An alternation's ways: one per choice when the choices can start
        alike, times the most its choices hold inside themselves."""
        key = id(item)
        cached = self._alt_weights.get(key)
        if cached is not None:
            return cached
        seen: Ranges = ()
        alike = False
        inside = 1
        for branch in item[1]:
            first = self.info(branch)[1]
            if _overlap(seen, first):
                alike = True
            seen = _union(seen, first)
            inside = max(
                inside, self._chain_cost(branch[1] if branch[0] == "seq" else [branch])
            )
        result = (len(item[1]) if alike else 1) * inside
        self._alt_weights[key] = result
        return result

    def _chain_cost(self, items: list) -> int:
        """The most work a sequence's variable repeats add up to: those that
        match the same characters multiply (``.*a.*a.*a`` is cubic,
        ``a?a?a?...a?aaa`` exponential), also across a mandatory character
        they can match themselves (the ``a``) and from inside optional groups
        and alternations (``a*(?:b|a*)(?:c|a*)x``)."""
        flat: list = []
        self._flatten(items, flat)
        chain: List[Tuple[int, Ranges, int]] = []  # (id, characters, ways)
        best = 1
        for entry in flat:
            if entry[0] == "atom":
                cost = entry[2]
                for _, other, ways in chain:
                    # (a character that had to be there between them, which
                    # the earlier repeat cannot match, keeps them apart)
                    if _overlap(other, entry[1]) and (
                        not entry[3] or _overlap(other, entry[3])
                    ):
                        cost *= ways
                best = max(best, cost)
                chain.append((entry[4], entry[1], entry[2]))
            elif entry[0] == "cut":
                chain = [c for c in chain if c[0] not in entry[1]]
            elif not any(_overlap(other, entry[1]) for _, other, _ in chain):
                chain = []  # a mandatory character the repeats cannot match
        return best

    def _adjacent(self, items: list) -> None:
        """The work of a sequence may not pass WORK_LIMIT: two overlapping
        unbounded repeats are the most. A pattern that does not start with
        ``^`` is tried at every start position of the answer, so its limit is
        divided by WORK_UNBOUNDED (about the longest answer tested)."""
        limit = WORK_LIMIT if self.anchored else WORK_LIMIT // WORK_UNBOUNDED
        if self._chain_cost(items) > limit:
            self.flag(ADJACENT_REPEATS)


def _anchored(node: tuple) -> bool:
    """Whether every way into the pattern starts with ``^`` (or ``\\A``)."""
    if node[0] == "bol":
        return True
    if node[0] == "alt":
        return all(_anchored(branch) for branch in node[1])
    if node[0] == "seq":
        for item in node[1]:
            if item[0] == "zero":
                continue  # a comment, \b
            return _anchored(item)
    return False


def pattern_hazard(pattern: Optional[str]) -> Optional[str]:
    """None when ``pattern`` is safe to evaluate with a backtracking engine,
    else the hazard code (``HAZARDS``)."""
    if not pattern:
        return None
    if len(pattern) > PATTERN_MAX_LENGTH:
        return TOO_COMPLEX
    parser = _Parser(pattern)
    try:
        tree = parser.parse()
    except (_TooDeep, RecursionError):
        return TOO_COMPLEX
    except _InlineFlags:
        return INLINE_FLAGS
    except _Unparseable:
        return UNPARSEABLE
    if parser.backref:
        return BACKREFERENCE
    analysis = _Analysis()
    analysis.anchored = _anchored(tree)
    try:
        analysis.walk(tree, (), False)
    except RecursionError:
        return TOO_COMPLEX
    return analysis.problem


def pattern_hazard_message(pattern: Optional[str]) -> Optional[str]:
    hazard = pattern_hazard(pattern)
    return HAZARD_MESSAGES[hazard] if hazard else None
