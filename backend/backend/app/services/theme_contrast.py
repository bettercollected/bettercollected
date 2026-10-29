"""WCAG 2.2 AA contrast of a form theme's own colours.

A port of the webapp's contrast guard (``webapp/src/utils/color-contrast.ts``
and ``themeContrastGuard`` in ``webapp/src/utils/theme-contrast.ts``), so a
form published through the API, the MCP server or with the AI assistant is
held to the same rules as one published from the builder. Keep the two in
step: ``docs/spec/theme-contrast.cases.json`` holds colour pairs and themes
with their expected ratios, failures and suggested colours, and both test
suites run every case.

Where the respondent form shows each role, and what it must reach:

- ``primary`` (questions and text): 4.5:1 on the page and in the white input
  boxes;
- ``secondary`` (buttons): white button text 4.5:1 on it, and 3:1 on the page
  for the chosen answer, icons and progress;
- ``tertiary`` (input borders): 3:1 on the page.

An outlined button (``buttonStyle`` ``outlined``) is not white text on the
button colour: its text and 2px edge are its *ink* (``outlined_button_ink``:
the button colour where it reads as text on the page, else the questions'
colour) on the page colour. So for an outlined theme the white-on-button rule
is replaced by measuring those real colours (``outlined``: the ink on the page
colour 4.5:1, its edge on the page 3:1); the chosen answer, icons and progress
(``action``) stay as they are.

"The page" is the background colour (``accent``), both stops of a gradient
and the white sheet of the ``margin`` pattern. Text over an image can't be
measured, so an image page has none (the input boxes and the buttons are
still checked).
"""

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

AA_TEXT = 4.5
AA_NON_TEXT = 3.0

WHITE = "#FFFFFF"
BLACK = "#000000"
_HEX_DIGITS = frozenset("0123456789abcdefABCDEF")

# Issue keys, in the order they are reported.
TEXT = "text"
ANSWER = "answer"
BUTTON = "button"
OUTLINED = "outlined"
BORDER = "border"
ACTION = "action"
ISSUE_ORDER = (TEXT, ANSWER, BUTTON, OUTLINED, BORDER, ACTION)
# The ink of an outlined button when the theme gives none of its own (the
# webapp's theme-root.ts inkOf / pageOf fallbacks).
DEFAULT_INK = "#101828"
ROLES = ("primary", "secondary", "tertiary")


def _get(obj: Any, key: str) -> Any:
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _js_round(value: float) -> int:
    """JavaScript's Math.round (halves go up), not Python's banker's round."""
    return math.floor(value + 0.5)


def hex_channels(value: Any) -> Optional[Tuple[int, int, int]]:
    """The 0-255 channels of a #rgb, #rrggbb or #rrggbbaa colour (alpha not
    blended), or None when it is none of them."""
    if not isinstance(value, str):
        return None
    digits = value.strip()
    if digits.startswith("#"):
        digits = digits[1:]
    if len(digits) not in (3, 6, 8) or not set(digits) <= _HEX_DIGITS:
        return None
    if len(digits) == 3:
        digits = "".join(d + d for d in digits)
    return tuple(int(digits[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def is_hex_colour(value: Any) -> bool:
    """A 6-digit hex colour, as a theme's roles are written."""
    return (
        isinstance(value, str)
        and len(value) == 7
        and value[0] == "#"
        and set(value[1:]) <= _HEX_DIGITS
    )


def relative_luminance(value: Any) -> float:
    """0 (black) to 1 (white); NaN for a colour that is not hex."""
    channels = hex_channels(value)
    if channels is None:
        return math.nan
    r, g, b = (
        v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
        for v in (c / 255 for c in channels)
    )
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: Any, b: Any) -> float:
    """Contrast ratio, 1 to 21, in either order; NaN when either colour is
    not hex (so every ``>=`` check on it fails)."""
    l1 = relative_luminance(a)
    l2 = relative_luminance(b)
    if math.isnan(l1) or math.isnan(l2):
        return math.nan
    return (max(l1, l2) + 0.05) / (min(l1, l2) + 0.05)


def mix_colours(a: Any, b: Any, weight: float) -> str:
    """``#RRGGBB`` of ``weight`` of ``a`` and the rest ``b``."""
    ca = hex_channels(a) or (0, 0, 0)
    cb = hex_channels(b) or (0, 0, 0)
    return "#" + "".join(
        f"{_js_round(x * weight + y * (1 - weight)):02X}" for x, y in zip(ca, cb)
    )


def display_ratio(ratio: float) -> str:
    """A ratio as people read it: one decimal, rounded down, so 4.47 never
    shows as 4.5."""
    return f"{math.floor(ratio * 10) / 10:.1f}"


@dataclass(frozen=True)
class ContrastIssue:
    key: str
    # The lowest ratio the pairing reaches over every ground it sits on.
    ratio: float
    minimum: float


@dataclass(frozen=True)
class ContrastGuard:
    # The failing pairings, in ISSUE_ORDER; empty when the theme passes.
    issues: List[ContrastIssue]
    # The nearest colours that pass every check, only the keys that change
    # (``primary``, ``secondary``, ``tertiary``, ``accent``, ``background``).
    # None when the theme passes.
    fix: Optional[Dict[str, Any]]
    # The page is an image: text on it can't be measured, only previewed.
    image_ground: bool


def _page_grounds(theme: Dict[str, Any]) -> List[str]:
    bg = theme.get("background")
    if _get(bg, "type") == "image" and _get(bg, "imageUrl"):
        return []
    grounds = [theme.get("accent")]
    if (
        _get(bg, "type") == "gradient"
        and _get(bg, "gradientFrom")
        and _get(bg, "gradientTo")
    ):
        grounds += [_get(bg, "gradientFrom"), _get(bg, "gradientTo")]
    if (
        _get(bg, "type") == "pattern"
        and _get(bg, "pattern") == "margin"
        and contrast(theme.get("primary"), WHITE) >= AA_TEXT
    ):
        grounds.append(WHITE)
    return grounds


def is_outlined(theme: Any) -> bool:
    """Does the theme draw its buttons outlined (text and edge, no fill)?"""
    return _get(theme, "buttonStyle") == "outlined"


def outlined_button_ink(theme: Any) -> str:
    """The text and 2px edge of an outlined button, on the page colour: the
    button colour where it reads as text there (4.5:1, which also clears the
    3:1 an edge needs), else the questions' colour. The webapp draws the same
    (``outlinedButtonInk`` in ``theme-root.ts``)."""
    page = _get(theme, "accent")
    page = page if is_hex_colour(page) else WHITE
    secondary = _get(theme, "secondary")
    if is_hex_colour(secondary) and contrast(secondary, page) >= AA_TEXT:
        return secondary
    primary = _get(theme, "primary")
    return primary if is_hex_colour(primary) else DEFAULT_INK


def _role_rules(
    grounds: List[str], outlined: bool = False
) -> Dict[str, List[Tuple[str, str, float]]]:
    """What each role must reach, and on what: ``(issue key, ground, minimum)``.
    An outlined button has no white text on the button colour; its real
    colours are measured by ``_outlined_failures``."""
    return {
        "primary": [(TEXT, ground, AA_TEXT) for ground in grounds]
        + [(ANSWER, WHITE, AA_TEXT)],
        "secondary": ([] if outlined else [(BUTTON, WHITE, AA_TEXT)])
        + [(ACTION, ground, AA_NON_TEXT) for ground in grounds],
        "tertiary": [(BORDER, ground, AA_NON_TEXT) for ground in grounds],
    }


def _outlined_rules(
    theme: Dict[str, Any], grounds: List[str]
) -> List[Tuple[str, str, str, float]]:
    """What an outlined button's real colours must reach:
    ``(issue key, colour, ground, minimum)``. Its text sits on the button's
    own background (the page colour) at 4.5:1; its edge sits against the page
    at 3:1."""
    ink = outlined_button_ink(theme)
    page = theme.get("accent")
    return [(OUTLINED, ink, page, AA_TEXT)] + [
        (OUTLINED, ink, ground, AA_NON_TEXT) for ground in grounds
    ]


def _failures(theme: Dict[str, Any], grounds: List[str]) -> List[ContrastIssue]:
    outlined = is_outlined(theme)
    rules = _role_rules(grounds, outlined)
    checks = [
        (key, theme.get(role), ground, minimum)
        for role in ROLES
        for key, ground, minimum in rules[role]
    ]
    if outlined:
        checks += _outlined_rules(theme, grounds)
    worst: Dict[str, ContrastIssue] = {}
    for key, colour, ground, minimum in checks:
        raw = contrast(colour, ground)
        ratio = 1.0 if math.isnan(raw) else raw
        if ratio >= minimum:
            continue
        seen = worst.get(key)
        if seen is None or ratio < seen.ratio:
            worst[key] = ContrastIssue(key, ratio, minimum)
    return [worst[key] for key in ISSUE_ORDER if key in worst]


def _to_hsl(value: str) -> Tuple[float, float, float]:
    r, g, b = (c / 255 for c in (hex_channels(value) or (128, 128, 128)))
    high = max(r, g, b)
    low = min(r, g, b)
    lightness = (high + low) / 2
    if high == low:
        return 0.0, 0.0, lightness
    d = high - low
    saturation = d / (2 - high - low) if lightness > 0.5 else d / (high + low)
    if high == r:
        hue = (g - b) / d + (6 if g < b else 0)
    elif high == g:
        hue = (b - r) / d + 2
    else:
        hue = (r - g) / d + 4
    return hue / 6, saturation, lightness


def _from_hsl(h: float, s: float, l: float) -> str:  # noqa: E741
    def hue(p: float, q: float, t: float) -> float:
        u = t + 1 if t < 0 else t - 1 if t > 1 else t
        if u < 1 / 6:
            return p + (q - p) * 6 * u
        if u < 1 / 2:
            return q
        if u < 2 / 3:
            return p + (q - p) * (2 / 3 - u) * 6
        return p

    q = l * (1 + s) if l < 0.5 else l + s - l * s
    p = 2 * l - q
    channels = (
        (l, l, l)
        if s == 0
        else (hue(p, q, h + 1 / 3), hue(p, q, h), hue(p, q, h - 1 / 3))
    )
    return "#" + "".join(f"{_js_round(c * 255):02X}" for c in channels)


def _nearest_passing(colour: Any, rules: List[Tuple[str, str, float]]) -> Optional[str]:
    """``colour``, or the nearest shade of it (same hue and saturation) that
    meets every rule; None when no shade does."""

    def passes(candidate: str) -> bool:
        return all(
            contrast(candidate, ground) >= minimum for _, ground, minimum in rules
        )

    start = colour if hex_channels(colour) else "#808080"
    if passes(start):
        return start
    h, s, l = _to_hsl(start)  # noqa: E741
    for step in range(1, 41):
        for lightness in (l - step / 40, l + step / 40):
            if lightness < 0 or lightness > 1:
                continue
            candidate = _from_hsl(h, s, lightness)
            if passes(candidate):
                return candidate
    if passes(BLACK):
        return BLACK
    if passes(WHITE):
        return WHITE
    return None


def _lighten_ground(theme: Dict[str, Any], weight: float) -> Dict[str, Any]:
    """The page colours ``weight`` of the way to white."""

    def lift(colour: Any) -> str:
        return mix_colours(WHITE, colour, weight) if hex_channels(colour) else WHITE

    bg = theme.get("background")
    ground: Dict[str, Any] = {"accent": lift(theme.get("accent"))}
    if (
        _get(bg, "type") == "gradient"
        and _get(bg, "gradientFrom")
        and _get(bg, "gradientTo")
    ):
        ground["background"] = {
            **_background_dict(bg),
            "gradientFrom": lift(_get(bg, "gradientFrom")),
            "gradientTo": lift(_get(bg, "gradientTo")),
        }
    return ground


def _background_dict(bg: Any) -> Dict[str, Any]:
    if isinstance(bg, dict):
        return dict(bg)
    dump = getattr(bg, "model_dump", None)
    return dump(exclude_none=True) if dump else {}


def _plain(theme: Any) -> Dict[str, Any]:
    return {
        key: _get(theme, key)
        for key in (
            "primary",
            "secondary",
            "tertiary",
            "accent",
            "background",
            "buttonStyle",
        )
    }


def theme_contrast_guard(theme: Any) -> ContrastGuard:
    """Every pairing of the theme's own colours that fails WCAG 2.2 AA (text
    4.5:1, controls 3:1) where the respondent form shows it, and the nearest
    colours that pass: the questions, button and border colours move first,
    each only as far as it must (keeping its hue); the page is lightened only
    when no colour reads on it and in the white input boxes at once."""
    plain = _plain(theme)
    grounds = _page_grounds(plain)
    image_ground = not grounds
    issues = _failures(plain, grounds)
    if not issues:
        return ContrastGuard(issues, None, image_ground)
    for weight in (0, 0.85, 0.92, 1):
        candidate = {**plain, **(_lighten_ground(plain, weight) if weight else {})}
        rules = _role_rules(_page_grounds(candidate), is_outlined(plain))
        moved = {role: _nearest_passing(plain[role], rules[role]) for role in ROLES}
        if None in moved.values():
            continue
        fixed = {**candidate, **moved}
        if _failures(fixed, _page_grounds(fixed)):
            continue
        fix = {
            role: fixed[role]
            for role in ("primary", "secondary", "tertiary", "accent")
            if fixed[role] != plain[role]
        }
        if fixed["background"] is not plain["background"]:
            fix["background"] = fixed["background"]
        return ContrastGuard(issues, fix, image_ground)
    # Unreachable for hex colours: on white, black text and a black border pass.
    return ContrastGuard(issues, None, image_ground)


def has_guarded_colours(theme: Any) -> bool:
    """A theme with its four colours, all 6-digit hex. One without them (an
    old form on the defaults) isn't checked."""
    return theme is not None and all(
        is_hex_colour(_get(theme, role))
        for role in ("primary", "secondary", "tertiary", "accent")
    )


def _colour(value: Any) -> Any:
    return value.upper() if isinstance(value, str) else value


def contrast_key(theme: Any) -> Tuple[Any, ...]:
    """Everything the contrast check reads from a theme: its four colours,
    whether its buttons are outlined, and what its background puts behind the
    text. Two themes with the same key get the same verdict, so "the theme
    changed" (publish_checks.theme_contrast_blocks) and "this saved theme is
    already stored" (form_themes) both compare keys. Mirrored by the webapp's
    ``contrastKey`` (utils/theme-contrast.ts)."""
    bg = _get(theme, "background")
    return (
        *(
            _colour(_get(theme, role))
            for role in ("primary", "secondary", "tertiary", "accent")
        ),
        is_outlined(theme),
        _get(bg, "type"),
        _colour(_get(bg, "gradientFrom")),
        _colour(_get(bg, "gradientTo")),
        _get(bg, "pattern"),
        bool(_get(bg, "imageUrl")),
    )
