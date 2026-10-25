"""Quality checks of an AI-generated or AI-edited form.

``check_form_quality(form, options)`` scores a ``StandardForm`` (what the
converter or the ops engine produced) and lists what is wrong with it, so a
prompt change can be measured: offline against the golden replies in
``tests/fixtures/ai_evals/`` and, opt-in, against a live provider
(``scripts/ai_eval.py``).

Pure and deterministic: no provider, no database, no clock. It reuses the
rules the product already enforces (``publish_checks`` for "why we ask" and
dead ends, ``image_urls`` for image hosts) and adds the ones a reviewer of
generated forms would apply (page length, duplicates, language, theme).

Findings carry codes, ids and page numbers, never the form's text, so a
report can be shared without quoting what was generated.
"""

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, FrozenSet, Iterable, List, Optional, Sequence, Tuple

from backend.app.constants.themes import NEW_FORM_THEME
from backend.app.services.image_urls import is_allowed_image_url
from backend.app.services.internal_fields import _get, _type_value, is_internal
from backend.app.services.publish_checks import (
    DISPLAY_ONLY_TYPES,
    MISSING_ENDING,
    MISSING_WHY_WE_ASK,
    PRESET_ANSWER,
    REQUIRED_UNANSWERABLE,
    THEME_CONTRAST,
    publish_problems,
    question_text,
)

ERROR = "error"
WARNING = "warning"
# What each finding costs out of 100.
PENALTY = {ERROR: 20, WARNING: 5}

DEFAULT_MAX_QUESTIONS_PER_PAGE = 8
# A form this long with every question required is asking too much.
ALL_REQUIRED_MIN_QUESTIONS = 6
JUMP_TARGET_SUBMIT = "__SUBMIT__"
SLIDE = "slide"
GROUP = "group"
CHOICE_TYPES = {"multiple_choice", "dropdown", "ranking"}

# Finding codes
MISSING_TITLE = "missing_title"
NO_QUESTIONS = "no_questions"
TOO_MANY_QUESTIONS_ON_PAGE = "too_many_questions_on_page"
TOO_MANY_QUESTIONS = "too_many_questions"
MISSING_FIELD_TYPE = "missing_field_type"
MISSING_SECTION_TITLES = "missing_section_titles"
WRONG_LANGUAGE = "wrong_language"
MIXED_LANGUAGE = "mixed_language"
DUPLICATE_QUESTION = "duplicate_question"
OPTIONAL_MARKED_REQUIRED = "optional_marked_required"
ALL_REQUIRED = "all_required"
TOO_FEW_CHOICES = "too_few_choices"
EXTERNAL_IMAGE = "external_image"
EXTERNAL_IMAGE_DROPPED = "external_image_dropped"
DANGLING_LOGIC_REFERENCE = "dangling_logic_reference"
THEME_NOT_DEFAULT = "theme_not_default"
THEME_REQUEST_IGNORED = "theme_request_ignored"
# from publish_checks, under the same codes
WHY_WE_ASK_MISSING = MISSING_WHY_WE_ASK

_OPTIONAL_TITLE = re.compile(
    r"\b(optional|optioneel|if applicable|indien van toepassing)\b", re.IGNORECASE
)


@dataclass(frozen=True)
class QualityOptions:
    """What the request asked for.

    ``language``: "en" or "nl" (None skips the check). ``theme_requested``:
    the request asked for other colours, a mood or a named theme, so a theme
    other than Leaflet is expected rather than a deviation.
    ``max_questions``: a cap the request set on the whole form ("make it
    short"). ``expected_types``: question types an unambiguous request
    implies (an email address asked for means an ``email`` question)."""

    language: Optional[str] = None
    theme_requested: bool = False
    max_questions_per_page: int = DEFAULT_MAX_QUESTIONS_PER_PAGE
    max_questions: Optional[int] = None
    expected_types: FrozenSet[str] = frozenset()


@dataclass(frozen=True)
class Finding:
    code: str
    severity: str
    message: str
    # field or page ids, page numbers (1-based) — never form text
    where: Tuple[str, ...] = ()


@dataclass
class QualityReport:
    score: int
    findings: List[Finding] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not any(f.severity == ERROR for f in self.findings)

    @property
    def codes(self) -> List[str]:
        return sorted(f.code for f in self.findings)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "score": self.score,
            "passed": self.passed,
            "findings": [
                {**asdict(f), "where": list(f.where)} for f in self.findings
            ],
        }


# ---------------------------------------------------------------------------
# Walking the form
# ---------------------------------------------------------------------------


def _pages(form: Any) -> List[Tuple[Optional[str], Any, List[Any]]]:
    """(page id, page, its top-level fields). A flat form (no slides) is one
    page without an id."""
    fields = _get(form, "fields") or []
    if any(_type_value(f) == SLIDE for f in fields):
        return [
            (_get(f, "id"), f, _get(_get(f, "properties"), "fields") or [])
            for f in fields
            if _type_value(f) == SLIDE
        ]
    return [(None, None, list(fields))]


def _expand(fields: Iterable[Any]) -> Iterable[Any]:
    """Fields with a group's children after the group."""
    for f in fields:
        yield f
        if _type_value(f) == GROUP:
            yield from _get(_get(f, "properties"), "fields") or []


def _is_question(f: Any) -> bool:
    """Respondent-facing and answerable: not display-only, not a group
    container, not internal."""
    kind = _type_value(f)
    return (
        kind not in DISPLAY_ONLY_TYPES
        and kind not in (GROUP, SLIDE)
        and not is_internal(f)
    )


def _questions(fields: Iterable[Any]) -> List[Any]:
    return [f for f in _expand(fields) if _is_question(f)]


def _all_questions(form: Any) -> List[Any]:
    return [q for _, _, fields in _pages(form) for q in _questions(fields)]


def _all_field_ids(form: Any) -> set:
    ids = set()
    for _, _, fields in _pages(form):
        for f in _expand(fields):
            if _get(f, "id"):
                ids.add(str(_get(f, "id")))
    return ids


def _required(f: Any) -> bool:
    return bool(_get(_get(f, "validations"), "required"))


def _is_leaflet(theme: Any) -> bool:
    return bool(theme) and (
        _get(theme, "style") == "leaflet" or _get(theme, "title") == NEW_FORM_THEME
    )


# ---------------------------------------------------------------------------
# Language (a small stop-word heuristic; there is no detector in the app)
# ---------------------------------------------------------------------------

# Words common in one language and rare or absent in the other.
_STOP_WORDS = {
    "en": frozenset(
        "the and you your yours what which how please with are this that would "
        "have does our about when any from will been there their they should "
        "could much many for who where why can into than".split()
    ),
    "nl": frozenset(
        "de het een en je jouw uw wat welke hoe graag met zijn deze dit wij ons "
        "onze over wanneer van niet ook bij naar wordt kunt heeft hebt waarom "
        "voor wie waar kun mag moet hier zal".split()
    ),
}
_WORD = re.compile(r"[a-zà-ÿ]+")
# Fewer hits than this: too little text to judge.
MIN_LANGUAGE_HITS = 4


def detect_language(text: str) -> Optional[str]:
    """"en", "nl", "mixed", or None when there is too little text."""
    words = _WORD.findall((text or "").lower())
    hits = {lang: sum(w in stop for w in words) for lang, stop in _STOP_WORDS.items()}
    if sum(hits.values()) < MIN_LANGUAGE_HITS:
        return None
    for lang, other in (("en", "nl"), ("nl", "en")):
        if hits[lang] >= 2 * hits[other] and hits[lang] > 0:
            return lang
    return "mixed"


def _choice_label(choice: Any) -> str:
    return str(_get(choice, "label") or _get(choice, "value") or "").strip()


def form_text(form: Any) -> str:
    """The respondent-visible text of a form (yes/no's fixed choices left
    out: the converter always adds them in English)."""
    parts: List[str] = [
        str(_get(form, "title") or ""),
        str(_get(form, "description") or ""),
    ]
    welcome = _get(form, "welcome_page")
    parts += [str(_get(welcome, "title") or ""), str(_get(welcome, "description") or "")]
    for _, page, fields in _pages(form):
        parts.append(str(_get(_get(page, "properties"), "section_title") or ""))
        for f in _expand(fields):
            props = _get(f, "properties")
            parts += [
                question_text(f),
                str(_get(f, "description") or ""),
                str(_get(props, "placeholder") or ""),
                str(_get(props, "why_we_ask") or ""),
            ]
            if _type_value(f) != "yes_no":
                parts += [_choice_label(c) for c in _get(props, "choices") or []]
    return "\n".join(p for p in parts if p)


# ---------------------------------------------------------------------------
# The checks
# ---------------------------------------------------------------------------


def _check_basics(form: Any) -> List[Finding]:
    findings = []
    if not str(_get(form, "title") or "").strip():
        findings.append(Finding(MISSING_TITLE, ERROR, "The form has no title."))
    if not _all_questions(form):
        findings.append(
            Finding(NO_QUESTIONS, ERROR, "The form has no question to answer.")
        )
    return findings


def _check_publish_rules(form: Any) -> List[Finding]:
    """The product's own publish checks: a reason on every identity
    question, no dead ends, no pre-ticked answers."""
    messages = {
        MISSING_WHY_WE_ASK: "A question asks for an email, phone or ID number "
        'without a "why we ask" reason.',
        REQUIRED_UNANSWERABLE: "A required question cannot be answered.",
        PRESET_ANSWER: "A choice question starts with an answer already chosen.",
        MISSING_ENDING: "A page jump goes to an ending that no longer exists.",
        THEME_CONTRAST: "The theme's colours are hard to read (WCAG AA contrast).",
    }
    return [
        Finding(
            problem["code"],
            ERROR,
            messages.get(problem["code"], problem["code"]),
            (str(problem.get("fieldId") or ""),),
        )
        for problem in publish_problems(form)
    ]


def _check_page_length(form: Any, limit: int) -> List[Finding]:
    findings = []
    for number, (page_id, _, fields) in enumerate(_pages(form), start=1):
        count = len(_questions(fields))
        if count > limit:
            findings.append(
                Finding(
                    TOO_MANY_QUESTIONS_ON_PAGE,
                    WARNING,
                    f"Page {number} has {count} questions (at most {limit}).",
                    (str(page_id or number),),
                )
            )
    return findings


def _check_request(form: Any, options: QualityOptions) -> List[Finding]:
    """What the request itself asked for: a length cap, question types."""
    questions = _all_questions(form)
    findings = []
    if options.max_questions is not None and len(questions) > options.max_questions:
        findings.append(
            Finding(
                TOO_MANY_QUESTIONS,
                ERROR,
                f"The form has {len(questions)} questions; the request asked "
                f"for at most {options.max_questions}.",
            )
        )
    present = {_type_value(q) for q in questions}
    for missing in sorted(set(options.expected_types) - present):
        findings.append(
            Finding(
                MISSING_FIELD_TYPE,
                ERROR,
                f"The request implies a '{missing}' question, and there is none.",
                (missing,),
            )
        )
    return findings


def _check_section_titles(form: Any) -> List[Finding]:
    if not _is_leaflet(_get(form, "theme")):
        return []
    pages = [p for p in _pages(form) if p[0] is not None and _questions(p[2])]
    if len(pages) < 2:
        return []
    missing = tuple(
        str(number)
        for number, (_, page, _) in enumerate(pages, start=1)
        if not str(_get(_get(page, "properties"), "section_title") or "").strip()
    )
    if not missing:
        return []
    return [
        Finding(
            MISSING_SECTION_TITLES,
            WARNING,
            f"{len(missing)} of {len(pages)} pages of a multi-page Leaflet form "
            "have no section title.",
            missing,
        )
    ]


def _check_language(form: Any, expected: Optional[str]) -> List[Finding]:
    if not expected:
        return []
    detected = detect_language(form_text(form))
    if detected is None or detected == expected:
        return []
    if detected == "mixed":
        return [
            Finding(
                MIXED_LANGUAGE,
                WARNING,
                f"The form mixes languages; '{expected}' was requested.",
            )
        ]
    return [
        Finding(
            WRONG_LANGUAGE,
            ERROR,
            f"The form reads as '{detected}'; '{expected}' was requested.",
        )
    ]


def _normalised(text: str) -> str:
    return " ".join(re.sub(r"[^\w\s]", " ", text.lower()).split())


def _check_duplicates(form: Any) -> List[Finding]:
    seen: Dict[str, str] = {}
    findings = []
    for q in _all_questions(form):
        key = _normalised(question_text(q))
        if not key:
            continue
        if key in seen:
            findings.append(
                Finding(
                    DUPLICATE_QUESTION,
                    ERROR,
                    "Two questions ask the same thing.",
                    (seen[key], str(_get(q, "id") or "")),
                )
            )
        else:
            seen[key] = str(_get(q, "id") or "")
    return findings


def _check_required(form: Any) -> List[Finding]:
    questions = _all_questions(form)
    findings = [
        Finding(
            OPTIONAL_MARKED_REQUIRED,
            WARNING,
            "A question that says it is optional is required.",
            (str(_get(q, "id") or ""),),
        )
        for q in questions
        if _required(q) and _OPTIONAL_TITLE.search(question_text(q))
    ]
    if len(questions) >= ALL_REQUIRED_MIN_QUESTIONS and all(
        _required(q) for q in questions
    ):
        findings.append(
            Finding(
                ALL_REQUIRED,
                WARNING,
                f"All {len(questions)} questions are required; keep optional "
                "what is not needed.",
            )
        )
    return findings


def _check_choices(form: Any) -> List[Finding]:
    findings = []
    for q in _all_questions(form):
        if _type_value(q) not in CHOICE_TYPES:
            continue
        labels = {
            _choice_label(c).lower()
            for c in _get(_get(q, "properties"), "choices") or []
        } - {""}
        if len(labels) < 2:
            findings.append(
                Finding(
                    TOO_FEW_CHOICES,
                    ERROR,
                    f"A choice question has {len(labels)} distinct option(s); "
                    "it needs at least 2.",
                    (str(_get(q, "id") or ""),),
                )
            )
    return findings


def _form_image_urls(form: Any) -> List[Tuple[str, str]]:
    """(where, url) of every image address the form would load."""
    urls = [
        ("cover_image", _get(form, "cover_image")),
        ("welcome_page", _get(_get(form, "welcome_page"), "imageUrl")),
        (
            "theme.background",
            _get(_get(_get(form, "theme"), "background"), "imageUrl"),
        ),
    ]
    for ending in _get(form, "thankyou_page") or []:
        urls.append(("thankyou_page", _get(ending, "imageUrl")))
    for page_id, page, fields in _pages(form):
        if page is not None:
            urls.append((str(page_id), _get(page, "image_url")))
        for f in _expand(fields):
            urls.append((str(_get(f, "id") or ""), _get(f, "image_url")))
    return [(where, url) for where, url in urls if isinstance(url, str) and url.strip()]


def _raw_image_urls(raw: Dict[str, Any]) -> List[Tuple[str, str]]:
    urls = [
        ("welcome_image_url", raw.get("welcome_image_url")),
        ("cover_image_url", raw.get("cover_image_url")),
    ]
    for number, slide in enumerate(raw.get("fields") or [], start=1):
        if isinstance(slide, dict):
            urls.append((f"page {number}", slide.get("image_url")))
    return [(where, url) for where, url in urls if isinstance(url, str) and url.strip()]


def _check_images(form: Any, raw: Optional[Dict[str, Any]]) -> List[Finding]:
    findings = [
        Finding(
            EXTERNAL_IMAGE,
            ERROR,
            "The form loads an image from a host other than our storage or Unsplash.",
            (where,),
        )
        for where, url in _form_image_urls(form)
        if not is_allowed_image_url(url)
    ]
    if raw:
        findings += [
            Finding(
                EXTERNAL_IMAGE_DROPPED,
                WARNING,
                "The model proposed an image from another host (it was dropped).",
                (where,),
            )
            for where, url in _raw_image_urls(raw)
            if not is_allowed_image_url(url)
        ]
    return findings


def _condition_refs(condition: Any) -> List[str]:
    refs = [
        _get(condition, "field_id") or _get(condition, "fieldId"),
        _get(condition, "child_field_id") or _get(condition, "childFieldId"),
    ]
    return [str(r) for r in refs if r]


def _check_logic(form: Any) -> List[Finding]:
    field_ids = _all_field_ids(form)
    page_ids = {str(p[0]) for p in _pages(form) if p[0] is not None}
    findings = []

    def dangling(refs: Sequence[str], where: str, what: str) -> None:
        for ref in refs:
            if ref not in field_ids:
                findings.append(
                    Finding(
                        DANGLING_LOGIC_REFERENCE,
                        ERROR,
                        f"{what} refers to a question that does not exist.",
                        (where, ref),
                    )
                )

    for page_id, page, fields in _pages(form):
        for jump in _get(_get(page, "properties"), "jumps") or []:
            for condition in _get(jump, "conditions") or []:
                dangling(_condition_refs(condition), str(page_id), "A page jump")
            target = _get(jump, "target")
            if target and target != JUMP_TARGET_SUBMIT and str(target) not in page_ids:
                findings.append(
                    Finding(
                        DANGLING_LOGIC_REFERENCE,
                        ERROR,
                        "A page jump goes to a page that does not exist.",
                        (str(page_id), str(target)),
                    )
                )
        for f in _expand(fields):
            logic = _get(_get(f, "properties"), "logic")
            for condition in _get(logic, "conditions") or []:
                dangling(
                    _condition_refs(condition),
                    str(_get(f, "id") or ""),
                    "A visibility rule",
                )
    return findings


def _check_theme(form: Any, theme_requested: bool) -> List[Finding]:
    leaflet = _is_leaflet(_get(form, "theme"))
    if theme_requested and leaflet:
        return [
            Finding(
                THEME_REQUEST_IGNORED,
                ERROR,
                "The request asked for another look, but the form kept Leaflet.",
            )
        ]
    if not theme_requested and not leaflet:
        return [
            Finding(
                THEME_NOT_DEFAULT,
                WARNING,
                "The form does not use the Leaflet default, and the request "
                "did not ask for another look.",
            )
        ]
    return []


def check_form_quality(
    form: Any,
    options: Optional[QualityOptions] = None,
    raw: Optional[Dict[str, Any]] = None,
) -> QualityReport:
    """Score ``form`` (a ``StandardForm`` or its dict) out of 100 and list
    its findings in a fixed order. ``raw``: the model's reply the form was
    converted from, when there was one (shows what the converter dropped)."""
    options = options or QualityOptions()
    findings: List[Finding] = []
    findings += _check_basics(form)
    findings += _check_publish_rules(form)
    findings += _check_page_length(form, options.max_questions_per_page)
    findings += _check_request(form, options)
    findings += _check_section_titles(form)
    findings += _check_language(form, options.language)
    findings += _check_duplicates(form)
    findings += _check_required(form)
    findings += _check_choices(form)
    findings += _check_images(form, raw)
    findings += _check_logic(form)
    findings += _check_theme(form, options.theme_requested)
    score = max(0, 100 - sum(PENALTY[f.severity] for f in findings))
    return QualityReport(score=score, findings=findings)
