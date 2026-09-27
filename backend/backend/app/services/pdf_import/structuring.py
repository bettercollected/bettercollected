"""Structuring: turn a page into the Form Document Model (FDM).

For each page the model gets the page image plus what the deterministic
stages found (words by id, layout primitives by id) and answers with
questions, sections and statements that reference those ids. Labels, options
and statements are rebuilt from the referenced words, so they keep the
document's own text; free text from the model is only accepted where the page
has no text layer (it was read from the image) and is marked as such.

An answer that references unknown ids, or is not valid, is retried once with
the errors; if it still fails (or no model is available) the page is
structured by deterministic rules instead, with low confidence, so no page is
ever lost. Values found in the document are never asked for or kept.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

FDM_VERSION = 1

QUESTION_KINDS = [
    "short_text",
    "long_text",
    "number",
    "email",
    "phone",
    "url",
    "date",
    "date_pair_bs_ad",
    "char_cells",
    "single_choice",
    "multi_choice",
    "yes_no",
    "consent",
    "file",
    "image",
    "signature",
    "thumbprint",
    "location_sketch",
    "table_fixed_rows",
    "table_open_rows",
]
INTERACTIVE = (
    "answer_slot",
    "cell_run",
    "checkbox",
    "table",
    "photo_box",
    "thumbprint_box",
    "area",
    "signature",
)

SYSTEM_PROMPT = """You convert one page of a paper form into structured questions.

You receive the page image and, when the page has a text layer, its words with
ids like w12 and its layout items with ids like p1-answer_slot-3 (answer
boxes, underlines, dotted lines, character cells, checkboxes, tables, photo and
thumbprint boxes, signatures, staff-only regions, paragraphs, section bars).

Rules:
- Every question, section title, option and statement must reference the ids
  of the words that make it up (label_refs, title_refs, refs). Never retype or
  translate the document's text when ids exist.
- Every answer place (answer_slot, cell_run, checkbox, table, photo_box,
  thumbprint_box, area, signature) belongs to exactly one question (slot_refs)
  or to a staff_only region, or is listed in ignore.
- Choice groups: checkboxes or "( )" next to labels become one single_choice or
  multi_choice question whose options reference their labels; an option like
  "Other" / "अन्य" followed by a blank is is_other=true.
- "If yes, mention ..." / "यदि भएमा ..." follow-ups: a yes_no question plus a
  follow-up question with follow_up_of = {question, when: "yes"}.
- Parts marked for office, bank or official use only are staff_only (refs =
  their layout item ids); do not make them questions.
- Declarations, instructions and terms are statements (legal=true for terms,
  declarations and consents); a declaration the applicant must accept becomes
  a consent question that references its statement.
- Paired B.S./A.D. (वि.सं./ई.सं.) dates are one date_pair_bs_ad question.
- Repeated blocks for several applicants: give each question applicant_index
  (1, 2, 3 ...), in the block's order.
- Page numbers, form codes and watermarks go in ignore.
- Never report values written or typed on the form: structure only.
- When the page has no text layer, give label/title/text as the exact text you
  read from the image, in its original language and script.
"""


def schema() -> dict:
    ref_list = {"type": "array", "items": {"type": "string"}}
    option = {
        "type": "object",
        "properties": {
            "refs": ref_list,
            "text": {"type": "string"},
            "is_other": {"type": "boolean"},
        },
        "required": ["refs"],
    }
    question = {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "kind": {"type": "string", "enum": QUESTION_KINDS},
            "label_refs": ref_list,
            "label": {"type": "string"},
            "help_refs": ref_list,
            "slot_refs": ref_list,
            "options": {"type": "array", "items": option},
            "required": {"type": ["boolean", "null"]},
            "section": {"type": ["string", "null"]},
            "follow_up_of": {
                "type": ["object", "null"],
                "properties": {
                    "question": {"type": "string"},
                    "when": {"type": "string"},
                },
            },
            "applicant_index": {"type": ["integer", "null"]},
            "statement": {"type": ["string", "null"]},
            "confidence": {"type": "number"},
        },
        "required": ["id", "kind"],
    }
    return {
        "type": "object",
        "properties": {
            "sections": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "title_refs": ref_list,
                        "title": {"type": "string"},
                        "continues_previous": {"type": "boolean"},
                    },
                    "required": ["id"],
                },
            },
            "questions": {"type": "array", "items": question},
            "statements": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "refs": ref_list,
                        "text": {"type": "string"},
                        "legal": {"type": "boolean"},
                        "section": {"type": ["string", "null"]},
                    },
                    "required": ["id"],
                },
            },
            "staff_only": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {"refs": ref_list, "heading_refs": ref_list},
                },
            },
            "ignore": ref_list,
        },
        "required": ["sections", "questions"],
    }


# --- page context --------------------------------------------------------------


@dataclass
class PageContext:
    number: int
    route: str
    words: List[dict]
    primitives: List[dict]
    has_text_layer: bool
    placeholders: set = field(default_factory=set)

    @property
    def primitive_ids(self) -> Dict[str, dict]:
        return {p["id"]: p for p in self.primitives}

    def word_text(self, refs: Sequence[str]) -> str:
        indices = [
            i
            for i in (_word_index(r) for r in refs)
            if i is not None and i < len(self.words)
        ]
        indices.sort(
            key=lambda i: (round(self.words[i]["top"] / 3), self.words[i]["x0"])
        )
        return " ".join(self.words[i]["text"] for i in indices)

    def words_of(self, primitive_id: str) -> List[str]:
        p = self.primitive_ids.get(primitive_id)
        return [f"w{i}" for i in (p or {}).get("words", [])]


def _word_index(ref: str) -> Optional[int]:
    m = re.fullmatch(r"w(\d+)", ref or "")
    return int(m.group(1)) if m else None


def expand_refs(refs: Sequence[str]) -> List[str]:
    """Accept ranges like "w12-w15" and "w12..w15" from the model."""
    out: List[str] = []
    for ref in refs or []:
        m = re.fullmatch(r"w(\d+)\s*(?:-|\.\.|–)\s*w?(\d+)", str(ref).strip())
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            out.extend(
                f"w{i}" for i in range(min(a, b), max(a, b) + 1) if abs(b - a) <= 2000
            )
        else:
            out.append(str(ref).strip())
    return out


def page_context(
    page_text: Optional[dict], page_layout: Optional[dict], number: int, route: str
) -> PageContext:
    words = (page_text or {}).get("words") or []
    usable = [w for w in words if w.get("source") != "untrusted"]
    primitives = (page_layout or {}).get("primitives") or []
    return PageContext(
        number=number,
        route=route,
        words=words,
        primitives=primitives,
        has_text_layer=route in ("text", "widgets") and bool(usable),
        placeholders=set((page_layout or {}).get("placeholder_words") or []),
    )


def describe(ctx: PageContext, max_words: int = 6000) -> str:
    """The page as the model sees it next to the image: lines of words by id,
    then the layout items with the words they contain."""
    lines: List[str] = [f"Page {ctx.number}."]
    if not ctx.has_text_layer:
        lines.append(
            "This page has no reliable text layer: read its text from the image. "
            "Give label, title and text fields as the exact text you read."
        )
        return "\n".join(lines)
    in_paragraph = {
        i for p in ctx.primitives if p["kind"] == "paragraph" for i in p["words"]
    }
    lines.append("Words (id:text), line by line:")
    row: List[str] = []
    last_top = None
    count = 0
    for i, w in sorted(
        enumerate(ctx.words), key=lambda iw: (round(iw[1]["top"] / 3), iw[1]["x0"])
    ):
        if i in in_paragraph:
            continue
        if w.get("source") == "untrusted":
            continue  # read from the image instead
        if last_top is not None and abs(w["top"] - last_top) > 3:
            lines.append(" ".join(row))
            row = []
        row.append(f"w{i}:{w['text']}")
        last_top = w["top"]
        count += 1
        if count >= max_words:
            break
    if row:
        lines.append(" ".join(row))
    lines.append("")
    lines.append("Layout items:")
    for p in ctx.primitives:
        extra = []
        for key in (
            "slot",
            "cell_kind",
            "cells",
            "source",
            "rows",
            "cols",
            "title",
            "heading",
            "placeholder",
            "label",
        ):
            if p.get(key) not in (None, "", []):
                extra.append(f"{key}={p[key]!r}")
        words = p.get("words") or []
        if p["kind"] == "paragraph":
            text = " ".join(ctx.words[i]["text"] for i in words[:60])
            span = f" words w{words[0]}..w{words[-1]}" if words else ""
            lines.append(f"- {p['id']} paragraph{span}: {text}…")
            continue
        wordrefs = (" words " + ",".join(f"w{i}" for i in words[:40])) if words else ""
        lines.append(
            f"- {p['id']} {p['kind']} at {p['bbox']}{wordrefs} {' '.join(extra)}".rstrip()
        )
    untrusted = [
        f"w{i}" for i, w in enumerate(ctx.words) if w.get("source") == "untrusted"
    ]
    if untrusted:
        lines.append("")
        lines.append(
            "Some lines of this page could not be read from its text layer: read those from the image "
            "and give their text in label/text fields."
        )
    return "\n".join(lines)


# --- validation ------------------------------------------------------------------


@dataclass
class PageResult:
    number: int
    source: str  # model | heuristic | none
    elements: List[dict] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


MAX_ITEMS_PER_KIND = 300  # sections, questions, statements... per page
MAX_REFS_PER_ITEM = 400
MAX_REFS_PER_PAGE = 6000
MAX_TEXT_CHARS = 500  # model-written label/title/option text


def _objects(answer: dict, key: str) -> List[dict]:
    """The dict items of a list in the model's answer; anything else is dropped."""
    items = answer.get(key)
    if not isinstance(items, list):
        return []
    return [item for item in items[:MAX_ITEMS_PER_KIND] if isinstance(item, dict)]


def _refs(value) -> List[str]:
    """A ref list from the model's answer: strings only, capped."""
    if not isinstance(value, list):
        return []
    return [ref for ref in value[:MAX_REFS_PER_ITEM] if isinstance(ref, str)]


def _text(value) -> str:
    return value.strip()[:MAX_TEXT_CHARS] if isinstance(value, str) else ""


def validate(answer: Any, ctx: PageContext) -> Tuple[List[dict], List[str], List[str]]:
    """(elements, errors, warnings). Errors make the answer unusable."""
    errors: List[str] = []
    warnings: List[str] = []
    if not isinstance(answer, dict):
        return [], ["the answer is not a JSON object"], []
    for key in ("sections", "questions", "statements", "staff_only", "ignore"):
        items = answer.get(key)
        wanted = str if key == "ignore" else dict
        if items is not None and (
            not isinstance(items, list)
            or not all(isinstance(item, wanted) for item in items)
        ):
            errors.append(
                f"{key}: must be a list of {'ids' if wanted is str else 'objects'}"
            )
    if errors:
        return [], errors, []
    prims = ctx.primitive_ids
    n_words = len(ctx.words)

    budget = [MAX_REFS_PER_PAGE]

    def check_refs(refs, where) -> List[str]:
        good = []
        expanded = expand_refs(refs)[: max(0, budget[0])]
        budget[0] -= len(expanded)
        for ref in expanded:
            idx = _word_index(ref)
            if idx is not None:
                if idx < n_words:
                    good.append(ref)
                else:
                    errors.append(f"{where}: unknown word id {ref}")
            elif ref in prims:
                good.extend(ctx.words_of(ref) or [ref])
            else:
                errors.append(f"{where}: unknown id {ref}")
        return good

    elements: List[dict] = []
    section_ids = set()
    for s in _objects(answer, "sections"):
        sid = str(s.get("id") or f"s{len(section_ids) + 1}")
        section_ids.add(sid)
        refs = check_refs(_refs(s.get("title_refs")), f"section {sid}")
        title = ctx.word_text(refs) if refs else _text(s.get("title"))
        if refs and not title:
            errors.append(f"section {sid}: empty title")
        grounded = bool(refs) or not ctx.has_text_layer
        elements.append(
            {
                "type": "section",
                "id": f"p{ctx.number}-{sid}",
                "title": title,
                "refs": refs,
                "continues_previous": bool(s.get("continues_previous")),
                "text_source": (
                    "document"
                    if refs
                    else ("image" if not ctx.has_text_layer else "model")
                ),
                "grounded": grounded,
            }
        )
    claimed: Dict[str, str] = {}
    question_ids = set()
    for q in _objects(answer, "questions"):
        qid = str(q.get("id") or f"q{len(question_ids) + 1}")
        question_ids.add(qid)
        kind = q.get("kind")
        if kind not in QUESTION_KINDS:
            errors.append(f"question {qid}: unknown kind {kind!r}")
            continue
        label_refs = check_refs(_refs(q.get("label_refs")), f"question {qid}")
        label = ctx.word_text(label_refs) if label_refs else _text(q.get("label"))
        if not label:
            errors.append(f"question {qid}: no label")
        if not label_refs and ctx.has_text_layer:
            warnings.append(f"question {qid}: label not grounded on the text layer")
        slot_refs = []
        for ref in _refs(q.get("slot_refs")):
            if ref not in prims:
                errors.append(f"question {qid}: unknown layout item {ref}")
                continue
            if ref in claimed and claimed[ref] != qid:
                warnings.append(f"{ref} claimed by {claimed[ref]} and {qid}")
            claimed[ref] = qid
            slot_refs.append(ref)
        options = []
        for o in _objects(q, "options"):
            orefs = check_refs(_refs(o.get("refs")), f"question {qid} option")
            text = ctx.word_text(orefs) if orefs else _text(o.get("text"))
            if text:
                options.append(
                    {"label": text, "refs": orefs, "is_other": bool(o.get("is_other"))}
                )
        if kind in ("single_choice", "multi_choice") and len(options) < 2:
            errors.append(f"question {qid}: a choice needs at least two options")
        confidence = q.get("confidence")
        confidence = float(confidence) if isinstance(confidence, (int, float)) else 0.7
        if not label_refs and ctx.has_text_layer:
            confidence = min(confidence, 0.5)
        elements.append(
            {
                "type": "question",
                "id": f"p{ctx.number}-{qid}",
                "kind": kind,
                "label": label,
                "label_refs": label_refs,
                "help": ctx.word_text(
                    check_refs(_refs(q.get("help_refs")), f"question {qid} help")
                )
                or None,
                "slot_refs": slot_refs,
                "options": options,
                "required": (
                    q.get("required") if isinstance(q.get("required"), bool) else None
                ),
                "section": (
                    f"p{ctx.number}-{q['section']}" if q.get("section") else None
                ),
                "follow_up_of": (
                    {
                        "question": f"p{ctx.number}-{q['follow_up_of'].get('question')}",
                        "when": str(q["follow_up_of"].get("when") or "yes"),
                    }
                    if isinstance(q.get("follow_up_of"), dict)
                    and q["follow_up_of"].get("question")
                    else None
                ),
                "applicant_index": (
                    q.get("applicant_index")
                    if isinstance(q.get("applicant_index"), int)
                    else None
                ),
                "statement": (
                    f"p{ctx.number}-{q['statement']}" if q.get("statement") else None
                ),
                "confidence": round(max(0.0, min(1.0, confidence)), 2),
                "text_source": (
                    "document"
                    if label_refs
                    else ("image" if not ctx.has_text_layer else "model")
                ),
            }
        )
    for st in _objects(answer, "statements"):
        sid = str(st.get("id") or f"t{len(elements) + 1}")
        refs = check_refs(_refs(st.get("refs")), f"statement {sid}")
        text = ctx.word_text(refs) if refs else _text(st.get("text"))
        if not text:
            continue
        elements.append(
            {
                "type": "statement",
                "id": f"p{ctx.number}-{sid}",
                "text": text,
                "refs": refs,
                "legal": bool(st.get("legal")),
                "section": (
                    f"p{ctx.number}-{st['section']}" if st.get("section") else None
                ),
                "text_source": (
                    "document"
                    if refs
                    else ("image" if not ctx.has_text_layer else "model")
                ),
            }
        )
    for so in _objects(answer, "staff_only"):
        refs = [r for r in (_refs(so.get("refs"))) if r in prims]
        for r in refs:
            claimed.setdefault(r, "staff_only")
        heading = ctx.word_text(check_refs(_refs(so.get("heading_refs")), "staff_only"))
        elements.append(
            {
                "type": "staff_only",
                "id": f"p{ctx.number}-staff-{len(elements) + 1}",
                "refs": refs,
                "heading": heading,
            }
        )
    for r in _refs(answer.get("ignore")):
        if r in prims:
            claimed.setdefault(r, "ignore")
    for p in ctx.primitives:
        if (
            p["kind"] in INTERACTIVE
            and p["id"] not in claimed
            and not _inside_staff(p, ctx)
        ):
            warnings.append(f"{p['id']} ({p['kind']}) was not assigned to a question")
    for e in elements:
        if (
            e["type"] == "question"
            and e.get("follow_up_of")
            and e["follow_up_of"]["question"] not in {x["id"] for x in elements}
        ):
            e["follow_up_of"] = None
            warnings.append(f"{e['id']}: follow-up of an unknown question dropped")
    return elements, errors, warnings


def _inside_staff(p: dict, ctx: PageContext) -> bool:
    for s in ctx.primitives:
        if s["kind"] == "staff_region":
            b, r = p["bbox"], s["bbox"]
            cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
            if r[0] <= cx <= r[2] and r[1] <= cy <= r[3]:
                return True
    return False


# --- deterministic fallback ---------------------------------------------------------


_EMAIL = re.compile(r"e-?mail|ईमेल|इमेल", re.I)
_PHONE = re.compile(r"phone|mobile|telephone|फोन|मोबाइल|टेलिफोन", re.I)
_DATE = re.compile(r"date|मिति|dob|birth", re.I)
_NUMBER = re.compile(r"\bno\.?$|number|नं\.?|संख्या|amount|रकम", re.I)


def _label_near(ctx: PageContext, box: Sequence[float], used: set) -> List[int]:
    """Words on the slot's line ending left of it, else the line just above."""
    x0, top, x1, bottom = box
    used = set(used) | ctx.placeholders
    same_line = [
        i
        for i, w in enumerate(ctx.words)
        if i not in used
        and w.get("source") != "untrusted"
        and abs((w["top"] + w["bottom"]) / 2 - (top + bottom) / 2)
        <= max(6, (bottom - top) / 2)
        and w["x1"] <= x0 + 2
        and x0 - w["x1"] <= 220
    ]
    if same_line:
        same_line.sort(key=lambda i: -ctx.words[i]["x1"])
        chosen, edge = [], x0
        for i in same_line:
            # the label may sit well left of its box; its own words are close together
            if edge - ctx.words[i]["x1"] > (120 if not chosen else 14):
                break
            chosen.append(i)
            edge = ctx.words[i]["x0"]
        return sorted(chosen, key=lambda i: ctx.words[i]["x0"])
    above = [
        i
        for i, w in enumerate(ctx.words)
        if i not in used
        and w.get("source") != "untrusted"
        and 0 <= top - w["bottom"] <= 16
        and w["x1"] >= x0 - 4
        and w["x0"] <= x1
    ]
    return sorted(above, key=lambda i: ctx.words[i]["x0"])


def _kind_for(label: str, primitive: dict) -> str:
    if primitive["kind"] == "cell_run":
        return "date" if primitive.get("cell_kind") == "date" else "char_cells"
    if primitive["kind"] in ("photo_box",):
        return "image"
    if primitive["kind"] == "thumbprint_box":
        return "thumbprint"
    if primitive["kind"] == "signature":
        return "signature"
    if primitive["kind"] == "area":
        return "long_text"
    if _EMAIL.search(label):
        return "email"
    if _PHONE.search(label):
        return "phone"
    if _DATE.search(label):
        return "date"
    if _NUMBER.search(label):
        return "short_text"
    return "short_text"


def heuristic(ctx: PageContext) -> List[dict]:
    """Structure a page from geometry alone: a label for every answer place,
    checkbox rows as choices, tables as tables, bars as sections."""
    if not ctx.has_text_layer:
        return []
    elements: List[dict] = []
    used: set = set()
    n = 0
    for p in ctx.primitives:
        if p["kind"] == "section_bar":
            used.update(p["words"])
            elements.append(
                {
                    "type": "section",
                    "id": f"p{ctx.number}-{p['id']}",
                    "title": p.get("title", ""),
                    "refs": [f"w{i}" for i in p["words"]],
                    "continues_previous": False,
                    "text_source": "document",
                    "grounded": True,
                }
            )
        elif p["kind"] == "staff_region":
            elements.append(
                {
                    "type": "staff_only",
                    "id": f"p{ctx.number}-{p['id']}",
                    "refs": [p["id"]],
                    "heading": p.get("heading", ""),
                }
            )
        elif p["kind"] == "paragraph":
            used.update(p["words"])
            text = " ".join(ctx.words[i]["text"] for i in p["words"])
            elements.append(
                {
                    "type": "statement",
                    "id": f"p{ctx.number}-{p['id']}",
                    "text": text,
                    "refs": [f"w{i}" for i in p["words"]],
                    "legal": True,
                    "section": None,
                    "text_source": "document",
                }
            )
    checkboxes = [
        p
        for p in ctx.primitives
        if p["kind"] == "checkbox" and not _inside_staff(p, ctx)
    ]
    rows: Dict[int, List[dict]] = {}
    for c in checkboxes:
        rows.setdefault(round(c["bbox"][1] / 6), []).append(c)
    for row in rows.values():
        row.sort(key=lambda c: c["bbox"][0])
        options = []
        for k, c in enumerate(row):
            right_edge = (
                row[k + 1]["bbox"][0] if k + 1 < len(row) else c["bbox"][2] + 160
            )
            words = [
                i
                for i, w in enumerate(ctx.words)
                if i not in used
                and i not in ctx.placeholders
                and w["x0"] >= c["bbox"][2] - 1
                and w["x1"] <= right_edge + 1
                and abs(
                    (w["top"] + w["bottom"]) / 2 - (c["bbox"][1] + c["bbox"][3]) / 2
                )
                <= 7
            ]
            used.update(words)
            text = " ".join(
                ctx.words[i]["text"]
                for i in sorted(words, key=lambda i: ctx.words[i]["x0"])
            )
            if text:
                options.append(
                    {
                        "label": text,
                        "refs": [f"w{i}" for i in words],
                        "is_other": bool(re.search(r"other|अन्य", text, re.I)),
                    }
                )
        label_words = _label_near(ctx, row[0]["bbox"], used)
        used.update(label_words)
        label = " ".join(ctx.words[i]["text"] for i in label_words) or (
            options[0]["label"] if len(options) == 1 else ""
        )
        n += 1
        kind = "single_choice" if len(options) >= 2 else "yes_no"
        elements.append(
            {
                "type": "question",
                "id": f"p{ctx.number}-h{n}",
                "kind": kind,
                "label": label or "Please choose",
                "label_refs": [f"w{i}" for i in label_words],
                "help": None,
                "slot_refs": [c["id"] for c in row],
                "options": options if kind == "single_choice" else [],
                "required": None,
                "section": None,
                "follow_up_of": None,
                "applicant_index": None,
                "statement": None,
                "confidence": 0.35,
                "text_source": "document" if label_words else "model",
            }
        )
    signature_slots = {
        p.get("slot")
        for p in ctx.primitives
        if p["kind"] == "signature" and p.get("slot")
    }
    for p in ctx.primitives:
        if p["kind"] not in (
            "answer_slot",
            "cell_run",
            "table",
            "photo_box",
            "thumbprint_box",
            "area",
            "signature",
        ) or _inside_staff(p, ctx):
            continue
        if p["id"] in signature_slots:
            continue  # the line a signature label points at: part of that signature
        if p["kind"] == "signature":
            label_words = list(p.get("words") or [])
        elif p["kind"] in ("photo_box", "thumbprint_box") and p.get("words"):
            label_words = list(p["words"])
        elif p["kind"] == "table":
            label_words = _label_near(ctx, p["bbox"], used)
        else:
            label_words = [i for i in _label_near(ctx, p["bbox"], used)]
        used.update(label_words)
        label = " ".join(ctx.words[i]["text"] for i in label_words)
        if p["kind"] == "table":
            kind = "table_open_rows" if not p.get("row_labels") else "table_fixed_rows"
            label = label or " / ".join(h for h in (p.get("header") or []) if h)
        else:
            kind = _kind_for(label, p)
        if p["kind"] == "signature":
            label = re.sub(r"[.…_]{3,}", "", label).strip() or "Signature"
        if not label:
            continue
        n += 1
        elements.append(
            {
                "type": "question",
                "id": f"p{ctx.number}-h{n}",
                "kind": kind,
                "label": label,
                "label_refs": [f"w{i}" for i in label_words],
                "help": None,
                "slot_refs": [p["id"]]
                + ([p["slot"]] if p["kind"] == "signature" and p.get("slot") else []),
                "options": [],
                "required": None,
                "section": None,
                "follow_up_of": None,
                "applicant_index": None,
                "statement": None,
                "confidence": 0.35,
                "text_source": "document",
                "table": (
                    {
                        "header": p.get("header"),
                        "row_labels": p.get("row_labels"),
                        "rows": p.get("rows"),
                        "cols": p.get("cols"),
                    }
                    if p["kind"] == "table"
                    else None
                ),
            }
        )
    return elements


# --- the stage ----------------------------------------------------------------------


async def structure_page(
    provider, ctx: PageContext, image_png: Optional[bytes]
) -> PageResult:
    """The model's structure for one page, validated; the deterministic
    fallback when there is no usable model answer."""
    if provider is not None and (
        ctx.has_text_layer
        or (image_png and getattr(provider, "supports_vision", False))
    ):
        prompt = describe(ctx)
        image = image_png if getattr(provider, "supports_vision", False) else None
        errors: List[str] = []
        for attempt in range(2):
            ask = (
                prompt
                if not errors
                else prompt
                + "\n\nYour previous answer had these problems; fix them:\n- "
                + "\n- ".join(errors[:20])
            )
            try:
                answer = await provider.analyze_page(
                    SYSTEM_PROMPT, ask, image, schema()
                )
            except Exception as error:  # noqa: BLE001 — provider errors fall back below
                errors = [f"provider error: {type(error).__name__}"]
                break
            try:
                elements, errors, warnings = validate(answer, ctx)
            except Exception as error:  # noqa: BLE001 — a malformed answer is unusable
                elements, warnings = [], []
                errors = [f"malformed answer: {type(error).__name__}"]
            if not errors:
                return PageResult(ctx.number, "model", elements, warnings)
        fallback = heuristic(ctx)
        return PageResult(
            ctx.number,
            "heuristic" if fallback else "none",
            fallback,
            [f"model answer unusable: {e}" for e in errors[:5]],
        )
    fallback = heuristic(ctx)
    reason = (
        "no model available"
        if provider is None
        else "the model cannot read page images"
    )
    return PageResult(
        ctx.number, "heuristic" if fallback else "none", fallback, [reason]
    )


def merge(pages: List[PageResult]) -> dict:
    """The whole document: sections continued across page breaks joined,
    signature/declaration lines repeated on every page reduced to one, and
    per-page provenance kept."""
    elements: List[dict] = []
    last_section: Optional[str] = None
    seen_signatures = set()
    for page in sorted(pages, key=lambda p: p.number):
        for e in page.elements:
            e = dict(e, page=page.number)
            if e["type"] == "section":
                if e.get("continues_previous") and last_section:
                    e["merged_into"] = last_section
                    continue
                last_section = e["id"]
            if e["type"] == "question":
                if not e.get("section") and last_section:
                    e["section"] = last_section
                if e["kind"] == "signature":
                    key = (e["label"].strip().lower(), e.get("applicant_index"))
                    if key in seen_signatures:
                        continue
                    seen_signatures.add(key)
            elements.append(e)
    return {
        "version": FDM_VERSION,
        "elements": elements,
        "pages": [
            {
                "number": p.number,
                "source": p.source,
                "elements": len(p.elements),
                "warnings": p.warnings,
            }
            for p in sorted(pages, key=lambda p: p.number)
        ],
    }
