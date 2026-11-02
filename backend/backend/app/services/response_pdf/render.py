"""Draws a PDF from a small document model: a title, a list of facts and
sections of questions with their answers. Text only.

What keeps this safe to run in the API process (docs/response-export.md, "PDF of
one submission"):

* **Text is data.** Everything is drawn with ``drawString`` (no ``Paragraph``
  markup, no XML parsing), so ``<b>``, ``&`` or ``%(x)s`` in an answer is just
  characters. Control and format characters are removed and a character the
  bundled font does not have prints as U+FFFD.
* **Nothing is fetched or embedded** except our own font file: no image, no
  link annotation, no URL dereferenced, no other font looked up.
* **Bounded.** Each answer is cut at ``MAX_VALUE_CHARS`` (by the caller), the
  document at ``MAX_PAGES`` pages (``PdfTooLarge``).

The document is *tagged*: every line is marked content, and a structure tree
(``Document`` > ``H1``, ``H2``, ``L`` > ``LI`` > ``Lbl`` + ``LBody``) names it in
reading order, with the document language and title set and page furniture
marked as artifacts. It is written in a second pass over our own bytes with
pypdf. It is not claimed to be PDF/UA-conformant: nothing here validates that.
"""

from __future__ import annotations

import io
import threading
import time
import unicodedata
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import List, Optional, Sequence, Tuple, Union

from pypdf import PdfReader, PdfWriter
from pypdf.generic import (
    ArrayObject,
    BooleanObject,
    DictionaryObject,
    NameObject,
    NumberObject,
    TextStringObject,
)
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

FONT_DIR = Path(__file__).resolve().parent / "fonts"
REGULAR = "BCDejaVuSans"
BOLD = "BCDejaVuSans-Bold"

PAGE_WIDTH, PAGE_HEIGHT = A4
MARGIN = 56.7  # 20 mm
CONTENT_WIDTH = PAGE_WIDTH - 2 * MARGIN
FOOTER_Y = 30.0
BOTTOM = MARGIN + 6

BODY_SIZE = 10.0
BODY_LEADING = 14.0
TITLE_SIZE = 18.0
HEADING_SIZE = 13.0
FOOTER_SIZE = 8.0
LABEL_COLUMN = 130.0
NESTED_INDENT = 14.0
INK = (0.1, 0.1, 0.1)
MUTED = (0.35, 0.35, 0.35)

MAX_PAGES = 200
MAX_VALUE_CHARS = 20_000
# all the text one document may lay out, and how long laying it out may take: a
# document past either is refused (``PdfTooLarge``), so no input holds a worker
MAX_TOTAL_CHARS = 500_000
MAX_LAYOUT_SECONDS = 10.0

_lock = threading.Lock()
_registered = False


class PdfTooLarge(Exception):
    """The document would run past ``MAX_PAGES`` pages."""


@dataclass
class Entry:
    """One labelled item: a question and its answer, or a fact. ``body`` is the
    answer text (newlines allowed), nested entries (a repeating group's items),
    or None (only the label). ``muted`` draws a body in the quiet colour (no answer)."""

    label: str
    body: Union[str, List["Entry"], None] = None
    muted: bool = False


@dataclass
class Section:
    heading: Optional[str]
    entries: List[Entry]


@dataclass
class PdfDocument:
    lang: str
    title: str  # the first heading and the document's title
    facts: List[Entry]
    sections: List[Section]
    footer: str  # left of the footer, on every page
    page_label: str  # "Page {n} of {total}"
    info_title: Optional[str] = None


# ----------------------------------------------------------------------- fonts


def _ensure_fonts() -> None:
    global _registered
    with _lock:
        if _registered:
            return
        pdfmetrics.registerFont(TTFont(REGULAR, str(FONT_DIR / "DejaVuSans.ttf")))
        pdfmetrics.registerFont(TTFont(BOLD, str(FONT_DIR / "DejaVuSans-Bold.ttf")))
        _registered = True


@lru_cache(maxsize=1)
def _glyphs() -> frozenset:
    _ensure_fonts()
    return frozenset(pdfmetrics.getFont(REGULAR).face.charToGlyph.keys()) & frozenset(
        pdfmetrics.getFont(BOLD).face.charToGlyph.keys()
    )


def clean_text(text: str) -> str:
    """``text`` as it can be drawn: no control or format character (newlines
    kept, tabs a space), and U+FFFD for a character the font lacks."""
    out = []
    glyphs = _glyphs()
    for ch in text:
        if ch == "\n":
            out.append(ch)
        elif ch in "\r\t ":
            out.append(" ")
        elif unicodedata.category(ch) in ("Cc", "Cf", "Cs", "Zl", "Zp", "Co", "Cn"):
            continue
        elif ord(ch) in glyphs and ord(ch) <= 0xFFFF:
            # (a character outside the Basic Multilingual Plane, an emoji, is not
            # mapped back to text reliably in a subset font: U+FFFD, like the rest)
            out.append(ch)
        else:
            out.append("�")
    return "".join(out)


@lru_cache(maxsize=4096)
def _char_width(ch: str, font: str, size: float) -> float:
    # the bundled fonts are registered by the first drawing; measuring may come first
    _ensure_fonts()
    return pdfmetrics.stringWidth(ch, font, size)


def text_width(text: str, font: str, size: float) -> float:
    return sum(_char_width(ch, font, size) for ch in text)


def ellipsize(text: str, font: str, size: float, width: float) -> str:
    """``text`` cut with an ellipsis so that it fits ``width``, in one pass over
    it (a form title has no length limit)."""
    room = width - _char_width("\u2026", font, size)
    used = 0.0
    cut = None
    for index, ch in enumerate(text):
        used += _char_width(ch, font, size)
        if cut is None and used > room:
            cut = index
        if used > width:
            return text[:cut].rstrip() + "\u2026"
    return text


def _break_word(word: str, font: str, size: float, width: float) -> List[str]:
    """``word`` cut between characters into pieces that fit ``width`` (one
    character at least per piece), in one pass over it."""
    pieces: List[str] = []
    used = 0.0
    start = 0
    for index, ch in enumerate(word):
        step = _char_width(ch, font, size)
        if used + step > width and index > start:
            pieces.append(word[start:index])
            start, used = index, 0.0
        used += step
    pieces.append(word[start:])
    return pieces


def wrap(text: str, font: str, size: float, width: float) -> List[str]:
    """Break ``text`` into lines that fit ``width``: at spaces, a word wider than
    a line broken between characters; newlines are kept."""
    lines: List[str] = []
    for paragraph in text.split("\n"):
        current = ""
        for word in paragraph.split(" "):
            candidate = word if not current else current + " " + word
            if text_width(candidate, font, size) <= width:
                current = candidate
                continue
            if current:
                lines.append(current)
                current = ""
            if text_width(word, font, size) > width:
                pieces = _break_word(word, font, size, width)
                lines.extend(pieces[:-1])
                word = pieces[-1]
            current = word
        lines.append(current)
    return lines


# ---------------------------------------------------------------------- layout


class Node:
    """An element of the structure tree. ``kids`` are nodes, or the
    ``(page index, MCID)`` of a line of marked content."""

    def __init__(self, tag: str):
        self.tag = tag
        self.kids: List[Union["Node", Tuple[int, int]]] = []

    def child(self, tag: str) -> "Node":
        node = Node(tag)
        self.kids.append(node)
        return node


@dataclass
class Placed:
    x: float
    y: float  # baseline
    text: str
    font: str
    size: float
    color: Tuple[float, float, float]
    node: Node


@dataclass
class Layout:
    root: Node = field(default_factory=lambda: Node("Document"))
    pages: List[List[Placed]] = field(default_factory=lambda: [[]])
    y: float = PAGE_HEIGHT - MARGIN
    chars: int = 0
    started: float = field(default_factory=time.monotonic)

    def spend(self, text: str) -> None:
        """Count ``text`` against the document's budget of characters and time."""
        self.chars += len(text)
        if self.chars > MAX_TOTAL_CHARS or time.monotonic() - self.started > MAX_LAYOUT_SECONDS:
            raise PdfTooLarge()

    def room(self, height: float) -> bool:
        return self.y - height >= BOTTOM

    def new_page(self) -> None:
        if len(self.pages) >= MAX_PAGES:
            raise PdfTooLarge()
        self.pages.append([])
        self.y = PAGE_HEIGHT - MARGIN

    def ensure(self, height: float) -> None:
        if not self.room(height):
            self.new_page()

    def skip(self, height: float) -> None:
        self.y -= height

    def lines(
        self,
        text: str,
        node: Node,
        x: float,
        width: float,
        font: str = REGULAR,
        size: float = BODY_SIZE,
        leading: float = BODY_LEADING,
        color: Tuple[float, float, float] = INK,
        keep: int = 2,
        reserve: float = 0.0,
    ) -> None:
        """Place ``text`` line by line under ``node``; the first ``keep`` lines
        stay together on a page, with ``reserve`` more room after them (a label
        never ends a page without the start of its answer)."""
        self.spend(text)
        rows = wrap(clean_text(text), font, size, width)
        for index, row in enumerate(rows):
            if index % 200 == 199:
                self.spend("")
            needed = leading * (min(keep, len(rows) - index) if index == 0 else 1)
            if index == 0:
                needed += reserve
            self.ensure(needed)
            self.y -= leading
            if row:
                self.pages[-1].append(Placed(x, self.y + (leading - size) / 2.2, row, font, size, color, node))


def _entry_stacked(layout: Layout, parent: Node, entry: Entry, x: float, width: float) -> None:
    item = parent.child("LI")
    label = item.child("Lbl")
    layout.lines(entry.label, label, x, width, BOLD, BODY_SIZE, BODY_LEADING, INK, keep=3, reserve=BODY_LEADING * 2)
    body = item.child("LBody")
    if isinstance(entry.body, list):
        nested = body.child("L")
        layout.skip(2)
        for sub in entry.body:
            _entry_stacked(layout, nested, sub, x + NESTED_INDENT, width - NESTED_INDENT)
    elif entry.body:
        layout.lines(entry.body, body, x, width, REGULAR, BODY_SIZE, BODY_LEADING, MUTED if entry.muted else INK)
    layout.skip(7)


def _entry_inline(layout: Layout, parent: Node, entry: Entry) -> None:
    """A fact: its label in a column on the left, its value beside it."""
    item = parent.child("LI")
    label = item.child("Lbl")
    body = item.child("LBody")
    layout.spend(entry.label)
    layout.spend(str(entry.body or ""))
    label_lines = wrap(clean_text(entry.label), BOLD, BODY_SIZE, LABEL_COLUMN - 8)
    value_lines = wrap(clean_text(str(entry.body or "")), REGULAR, BODY_SIZE, CONTENT_WIDTH - LABEL_COLUMN)
    rows = max(len(label_lines), len(value_lines))
    layout.ensure(BODY_LEADING * min(rows, 2))
    for index in range(rows):
        layout.ensure(BODY_LEADING)
        layout.y -= BODY_LEADING
        baseline = layout.y + (BODY_LEADING - BODY_SIZE) / 2.2
        if index < len(label_lines) and label_lines[index]:
            layout.pages[-1].append(Placed(MARGIN, baseline, label_lines[index], BOLD, BODY_SIZE, INK, label))
        if index < len(value_lines) and value_lines[index]:
            layout.pages[-1].append(
                Placed(MARGIN + LABEL_COLUMN, baseline, value_lines[index], REGULAR, BODY_SIZE, MUTED if entry.muted else INK, body)
            )
    layout.skip(3)


def build_layout(document: PdfDocument) -> Layout:
    _ensure_fonts()
    layout = Layout()
    title = layout.root.child("H1")
    layout.lines(document.title, title, MARGIN, CONTENT_WIDTH, BOLD, TITLE_SIZE, TITLE_SIZE + 6, INK, keep=1)
    layout.skip(8)
    if document.facts:
        facts = layout.root.child("L")
        for fact in document.facts:
            _entry_inline(layout, facts, fact)
        layout.skip(8)
    for section in document.sections:
        if section.heading:
            layout.ensure(HEADING_SIZE + 6 + BODY_LEADING * 2)
            layout.skip(6)
            heading = layout.root.child("H2")
            layout.lines(section.heading, heading, MARGIN, CONTENT_WIDTH, BOLD, HEADING_SIZE, HEADING_SIZE + 4, INK, keep=1)
            layout.skip(4)
        entries = layout.root.child("L")
        for entry in section.entries:
            _entry_stacked(layout, entries, entry, MARGIN, CONTENT_WIDTH)
    return layout


# --------------------------------------------------------------------- drawing


def _draw(document: PdfDocument, layout: Layout) -> bytes:
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4, pageCompression=1, lang=document.lang)
    pdf.setTitle(clean_text(document.info_title or document.title).replace("\n", " "))
    pdf.setAuthor("")
    pdf.setCreator("BetterCollected")
    pdf.setProducer("BetterCollected")
    total = len(layout.pages)
    footer = ellipsize(clean_text(document.footer.replace("\n", " ")), REGULAR, FOOTER_SIZE, CONTENT_WIDTH - 90)
    for index, page in enumerate(layout.pages):
        mcid = 0
        for line in page:
            pdf.setFont(line.font, line.size)
            pdf.setFillColorRGB(*line.color)
            tag = line.node.tag
            # ``Canvas._code`` is private: marked content has no public hook in ReportLab.
            # The version is pinned (pyproject.toml) and ``test_the_private_canvas_hook_still_exists``
            # fails when an upgrade moves it
            pdf._code.append(f"/{tag} << /MCID {mcid} >> BDC")
            pdf.drawString(line.x, line.y, line.text)
            pdf._code.append("EMC")
            line.node.kids.append((index, mcid))
            mcid += 1
        # page furniture: an artifact, not content
        pdf._code.append("/Artifact << /Type /Pagination >> BDC")
        pdf.setFont(REGULAR, FOOTER_SIZE)
        pdf.setFillColorRGB(*MUTED)
        pdf.drawString(MARGIN, FOOTER_Y, footer)
        number = clean_text(document.page_label.format(n=index + 1, total=total))
        pdf.drawRightString(PAGE_WIDTH - MARGIN, FOOTER_Y, number)
        pdf._code.append("EMC")
        pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def _structure(data: bytes, layout: Layout, document: PdfDocument) -> bytes:
    """Add the structure tree, the language, the title display flag and the
    parent tree to our own PDF."""
    reader = PdfReader(io.BytesIO(data))
    writer = PdfWriter(clone_from=reader)
    page_refs = [page.indirect_reference for page in writer.pages]
    root = DictionaryObject()
    root_ref = writer._add_object(root)
    parents: List[List] = [[] for _ in page_refs]

    def build(node: Node, parent_ref) -> object:
        element = DictionaryObject()
        ref = writer._add_object(element)
        element[NameObject("/Type")] = NameObject("/StructElem")
        element[NameObject("/S")] = NameObject("/" + node.tag)
        element[NameObject("/P")] = parent_ref
        content = [k for k in node.kids if isinstance(k, tuple)]
        children = [k for k in node.kids if isinstance(k, Node)]
        kids = ArrayObject()
        if content:
            pages = {p for p, _ in content}
            if len(pages) == 1:
                element[NameObject("/Pg")] = page_refs[content[0][0]]
                for _, mcid in content:
                    kids.append(NumberObject(mcid))
            else:
                for page, mcid in content:
                    kids.append(
                        DictionaryObject(
                            {
                                NameObject("/Type"): NameObject("/MCR"),
                                NameObject("/Pg"): page_refs[page],
                                NameObject("/MCID"): NumberObject(mcid),
                            }
                        )
                    )
            for page, mcid in content:
                # the parent tree maps a page's marked content to its element, by MCID
                while len(parents[page]) <= mcid:
                    parents[page].append(None)
                parents[page][mcid] = ref
        for child in children:
            kids.append(build(child, ref))
        element[NameObject("/K")] = kids
        return ref

    document_ref = build(layout.root, root_ref)
    nums = ArrayObject()
    for index, refs in enumerate(parents):
        nums.append(NumberObject(index))
        nums.append(ArrayObject([r for r in refs if r is not None]))
    root[NameObject("/Type")] = NameObject("/StructTreeRoot")
    root[NameObject("/K")] = document_ref
    root[NameObject("/ParentTree")] = DictionaryObject({NameObject("/Nums"): nums})
    root[NameObject("/ParentTreeNextKey")] = NumberObject(len(parents))
    for index, page in enumerate(writer.pages):
        page[NameObject("/StructParents")] = NumberObject(index)
    catalog = writer._root_object
    catalog[NameObject("/StructTreeRoot")] = root_ref
    catalog[NameObject("/MarkInfo")] = DictionaryObject({NameObject("/Marked"): BooleanObject(True)})
    catalog[NameObject("/ViewerPreferences")] = DictionaryObject({NameObject("/DisplayDocTitle"): BooleanObject(True)})
    catalog[NameObject("/Lang")] = TextStringObject(document.lang)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def render_pdf(document: PdfDocument) -> bytes:
    """The PDF's bytes. Raises ``PdfTooLarge`` past ``MAX_PAGES`` pages."""
    layout = build_layout(document)
    return _structure(_draw(document, layout), layout, document)
