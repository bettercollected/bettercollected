"""Layout primitives: the deterministic geometry of a form page.

From the vector drawing and the recovered words (``text_layer``) this finds
what a person filling the paper form would see:

    section_bar     a coloured or dark band with a heading in it
    answer_slot     an empty box, an underline or a run of leader dots
    cell_run        N equal adjacent boxes: one character each (account no., DD MM YYYY)
    checkbox        a small square, "( )" or a box glyph
    table           a ruled grid with at least two rows and two columns
    photo_box       a portrait frame labelled "photo"
    thumbprint_box  a frame for a thumb impression
    area            a large empty frame (a map, remarks, a stamp)
    signature       a signature label and the line or dots it points at
    staff_region    a "for office use only" part of the page
    paragraph       a block of running text (instructions, declarations, terms)
    logo, watermark images

Every primitive references the words it contains by their index in the page's
word list, so later stages ground labels on the document's own text.

Import-safe for the sandbox child: no imports from the backend package.
"""

from __future__ import annotations

import io
import re
from typing import Dict, List, Optional, Sequence, Tuple

from .text_layer import page_words

Box = Tuple[float, float, float, float]  # x0, top, x1, bottom

# geometry thresholds (PDF points)
MIN_SIDE = 3.0
CHECKBOX_MIN, CHECKBOX_MAX = 6.0, 20.0
CELL_MAX_WIDTH = 30.0
CELL_MIN_HEIGHT, CELL_MAX_HEIGHT = 8.0, 30.0
CELL_GAP = 4.0
SLOT_MIN_WIDTH = 30.0
SLOT_MAX_HEIGHT = 60.0
UNDERLINE_MIN_WIDTH = 40.0
BAR_MIN_WIDTH, BAR_MIN_HEIGHT, BAR_MAX_HEIGHT = 60.0, 8.0, 40.0
PARAGRAPH_MIN_WORDS = 20

PLACEHOLDER_WORDS = {"dd", "mm", "yy", "yyyy", "d", "m", "y", "dd/mm/yyyy"}
PHOTO_WORDS = ("photo", "फोटो", "photograph", "passport size")
THUMB_WORDS = ("thumb", "औंठा", "right", "left", "दाँया", "बाँया", "दायाँ", "बायाँ")
SIGNATURE_WORDS = (
    "signature",
    "signed",
    "sign",
    "हस्ताक्षर",
    "दस्तखत",
    "firma",
    "unterschrift",
)
STAFF_PHRASES = (
    "for office use only",
    "for official use only",
    "office use only",
    "official use only",
    "for bank's use only",
    "for bank’s use only",
    "for bank use only",
    "bank use only",
    "for internal use only",
    "प्रयोजनको लागि मात्र",
    "कार्यालय प्रयोजनको लागि",
    "कार्यालयको लागि मात्र",
)
_DOTS = re.compile(r"^[.…·_‥]{4,}$")
_TRAILING_DOTS = re.compile(r"^(.*?)([.…·_‥]{4,})$")
_LEADING_DOTS = re.compile(r"^([.…·_‥]{4,})(.*)$")
BOX_GLYPHS = set("☐□❑❒◻▢⬜")
TICK_GLYPHS = set("✓✔☑☒")


# --- small geometry helpers ------------------------------------------------------


def _box(obj) -> Box:
    return (float(obj["x0"]), float(obj["top"]), float(obj["x1"]), float(obj["bottom"]))


def _w(b: Box) -> float:
    return b[2] - b[0]


def _h(b: Box) -> float:
    return b[3] - b[1]


def _area(b: Box) -> float:
    return max(0.0, _w(b)) * max(0.0, _h(b))


def _inside(inner: Box, outer: Box, pad: float = 1.5) -> bool:
    return (
        inner[0] >= outer[0] - pad
        and inner[1] >= outer[1] - pad
        and inner[2] <= outer[2] + pad
        and inner[3] <= outer[3] + pad
    )


def _centre_inside(inner: Box, outer: Box) -> bool:
    cx, cy = (inner[0] + inner[2]) / 2, (inner[1] + inner[3]) / 2
    return outer[0] <= cx <= outer[2] and outer[1] <= cy <= outer[3]


def _iou(a: Box, b: Box) -> float:
    x0, y0, x1, y1 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    inter = _area((x0, y0, x1, y1)) if x1 > x0 and y1 > y0 else 0.0
    union = _area(a) + _area(b) - inter
    return inter / union if union else 0.0


def _union(boxes: Sequence[Box]) -> Box:
    return (
        min(b[0] for b in boxes),
        min(b[1] for b in boxes),
        max(b[2] for b in boxes),
        max(b[3] for b in boxes),
    )


def _r(b: Box) -> List[float]:
    return [round(v, 1) for v in b]


def _rgb(hex_colour: Optional[str]) -> Optional[Tuple[float, float, float]]:
    if not hex_colour or len(hex_colour) != 7:
        return None
    return tuple(int(hex_colour[i : i + 2], 16) / 255 for i in (1, 3, 5))  # type: ignore[return-value]


def _luminance(rgb) -> float:
    r, g, b = rgb
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _saturation(rgb) -> float:
    return max(rgb) - min(rgb)


def _colour(value) -> Optional[str]:
    from .text_layer import colour_hex

    return colour_hex(value)


# --- the page ------------------------------------------------------------------


class _Page:
    def __init__(self, page, words: List[dict]):
        self.page = page
        self.width, self.height = float(page.width), float(page.height)
        self.words = words
        self.boxes = [(w["x0"], w["top"], w["x1"], w["bottom"]) for w in words]
        self.used_words: set = set()
        self.primitives: List[dict] = []
        self._counters: Dict[str, int] = {}

    def add(self, kind: str, box: Box, words: Sequence[int] = (), **attrs) -> dict:
        n = self._counters.get(kind, 0) + 1
        self._counters[kind] = n
        primitive = {
            "id": f"p{self.page.page_number}-{kind}-{n}",
            "kind": kind,
            "bbox": _r(box),
            "words": sorted(words),
            **attrs,
        }
        self.primitives.append(primitive)
        return primitive

    def words_in(self, box: Box, pad: float = 1.5) -> List[int]:
        return [
            i
            for i, b in enumerate(self.boxes)
            if _centre_inside(
                b, (box[0] - pad, box[1] - pad, box[2] + pad, box[3] + pad)
            )
        ]

    def text(self, indices: Sequence[int]) -> str:
        return " ".join(
            self.words[i]["text"]
            for i in sorted(
                indices, key=lambda i: (round(self.boxes[i][1]), self.boxes[i][0])
            )
        )

    def is_placeholder(self, index: int) -> bool:
        word = self.words[index]
        if word["text"].strip().lower() in PLACEHOLDER_WORDS:
            return True
        rgb = _rgb(word.get("colour"))
        return (
            rgb is not None
            and 0.55 <= _luminance(rgb) <= 0.93
            and _saturation(rgb) < 0.2
        )


# --- detectors -------------------------------------------------------------------


def _rects(pg: _Page) -> List[dict]:
    """Rectangles, deduplicated: many producers draw each box twice (fill, stroke)."""
    page_area = pg.width * pg.height
    merged: Dict[Tuple[int, int, int, int], dict] = {}
    for r in pg.page.rects:
        b = _box(r)
        if _w(b) < MIN_SIDE or _h(b) < MIN_SIDE or _area(b) > 0.8 * page_area:
            continue
        key = tuple(round(v) for v in b)
        entry = merged.setdefault(key, {"box": b, "fill": None, "stroke": False})
        if r.get("fill"):
            entry["fill"] = _colour(r.get("non_stroking_color")) or entry["fill"]
        if r.get("stroke"):
            entry["stroke"] = True
    return list(merged.values())


def _all_outlines(pg: _Page) -> List[dict]:
    """Every stroked rectangle, including large frames around groups of fields."""
    page_area = pg.width * pg.height
    return [
        {"box": _box(r)}
        for r in pg.page.rects
        if r.get("stroke")
        and _area(_box(r)) <= 0.8 * page_area
        and _w(_box(r)) >= 40
        and _h(_box(r)) >= 20
    ]


def _grid_cells(pg: _Page) -> Tuple[List[Box], List[dict]]:
    """Boxes and tables drawn with lines (pdfplumber's table finder)."""
    boxes, tables = [], []
    try:
        found = pg.page.find_tables(
            {"vertical_strategy": "lines", "horizontal_strategy": "lines"}
        )
    except Exception:  # noqa: BLE001 — a degenerate drawing yields no grid
        return boxes, tables
    for table in found:
        rows = [[c for c in row.cells] for row in table.rows]
        n_rows = len(rows)
        n_cols = max((len(r) for r in rows), default=0)
        cells = [c for row in rows for c in row if c]
        if n_rows >= 2 and n_cols >= 2 and _is_data_table(pg, rows):
            tables.append({"box": tuple(table.bbox), "rows": rows})
        else:
            boxes.extend(tuple(c) for c in cells)
    return boxes, tables


def _is_data_table(pg: _Page, rows) -> bool:
    """A data table has a header row whose cells all carry text, and at least
    one later row that is (mostly) empty, waiting to be filled. A grid of
    label boxes next to answer boxes is page layout instead."""

    def texts(row):
        return [
            (
                bool([i for i in pg.words_in(tuple(c)) if not pg.is_placeholder(i)])
                if c
                else None
            )
            for c in row
        ]

    header = texts(rows[0])
    present = [t for t in header if t is not None]
    if len(present) < 2 or not all(present):
        return False
    widths = {len([c for c in r if c]) for r in rows}
    if len(widths) > 2:
        return False
    for row in rows[1:]:
        cells = [t for t in texts(row) if t is not None]
        if cells and sum(1 for t in cells if not t) >= max(1, len(cells) // 2):
            return True
    return False


def _filled_shapes(pg: _Page) -> List[dict]:
    """Filled curves and polygons (slanted or rounded header bands), as boxes."""
    shapes = []
    for c in pg.page.curves:
        if not c.get("fill"):
            continue
        b = _box(c)
        if _w(b) >= MIN_SIDE and _h(b) >= MIN_SIDE:
            shapes.append(
                {
                    "box": b,
                    "fill": _colour(c.get("non_stroking_color")),
                    "stroke": False,
                }
            )
    return shapes


def _title_beside(pg: _Page, band: Box) -> List[int]:
    """Words on the band's line that end just before it, chained leftwards."""
    top, bottom = band[1] - 4, band[3] + 4
    row = sorted(
        (
            i
            for i, b in enumerate(pg.boxes)
            if b[1] >= top
            and b[3] <= bottom
            and b[2] <= band[0] + 2
            and i not in pg.used_words
        ),
        key=lambda i: -pg.boxes[i][2],
    )
    chosen: List[int] = []
    edge = band[0]
    for i in row:
        if edge - pg.boxes[i][2] > 14:
            break
        chosen.append(i)
        edge = pg.boxes[i][0]
    return chosen


def _section_bars(
    pg: _Page, rects: List[dict], exclude: Sequence[Box] = ()
) -> List[dict]:
    bars = []
    seen: List[Box] = []
    for r in rects + _filled_shapes(pg):
        if any(_inside(r["box"], t) for t in exclude):
            continue  # a coloured header cell of a table, not a section heading
        rgb = _rgb(r["fill"])
        b = r["box"]
        if (
            rgb is None
            or not (BAR_MIN_HEIGHT <= _h(b) <= BAR_MAX_HEIGHT)
            or _w(b) < BAR_MIN_WIDTH
        ):
            continue
        if _luminance(rgb) > 0.85 and _saturation(rgb) < 0.15:
            continue  # white or light grey: a box, not a bar
        words = [
            i
            for i in pg.words_in(b)
            if not pg.is_placeholder(i) and i not in pg.used_words
        ]
        if not words and _w(b) >= 0.25 * pg.width:
            # a band that starts right of its heading: the title sits beside it
            words = _title_beside(pg, b)
            if words:
                b = _union([b] + [pg.boxes[i] for i in words])
        if not words or any(_iou(b, s) > 0.6 for s in seen):
            continue
        seen.append(b)
        bars.append(
            pg.add("section_bar", b, words, title=pg.text(words), fill=r["fill"])
        )
        pg.used_words.update(words)
    return bars


def _dedupe(boxes: List[Box]) -> List[Box]:
    out: List[Box] = []
    for b in sorted(boxes, key=lambda b: (round(b[1]), b[0], -_area(b))):
        if not any(_iou(b, o) > 0.85 for o in out):
            out.append(b)
    return out


_DMY = re.compile(r"^[DMY]+$")


def _is_date_box(pg: _Page, b: Box) -> bool:
    words = pg.words_in(b)
    text = "".join(pg.words[i]["text"] for i in words).upper().replace(" ", "")
    return (
        bool(words)
        and all(pg.is_placeholder(i) for i in words)
        and bool(_DMY.match(text))
    )


def _cell_runs(pg: _Page, boxes: List[Box]) -> List[Box]:
    small = sorted(
        (
            b
            for b in boxes
            if CELL_MIN_HEIGHT <= _h(b) <= CELL_MAX_HEIGHT
            and (_w(b) <= CELL_MAX_WIDTH or (_w(b) <= 70 and _is_date_box(pg, b)))
        ),
        key=lambda b: (round(b[1]), b[0]),
    )
    used: List[Box] = []
    run: List[Box] = []

    def flush():
        if len(run) >= 3:
            box = _union(run)
            words = pg.words_in(box)
            hints = [pg.words[i]["text"] for i in words]
            joined = "".join(hints).upper().replace(" ", "")
            kind = (
                "date"
                if joined and _DMY.match(joined) and "Y" in joined
                else "characters"
            )
            pg.add(
                "cell_run",
                box,
                words,
                cells=len(run),
                cell_kind=kind,
                placeholder=" ".join(hints) or None,
            )
            pg.used_words.update(words)
            used.extend(run)

    for b in small:
        same_row = (
            bool(run)
            and abs(b[1] - run[-1][1]) <= 1.5
            and abs(_h(b) - _h(run[-1])) <= 2.0
        )
        if same_row and b[0] < run[-1][2] - 3:
            continue  # the same cell drawn twice, slightly offset
        if same_row and -3.0 <= b[0] - run[-1][2] <= CELL_GAP:
            run.append(b)
        else:
            flush()
            run = [b]
    flush()

    return used


def _classify_boxes(
    pg: _Page, boxes: List[Box], taken: List[Box], runs: Sequence[Box] = ()
) -> List[Box]:
    slots = []
    for b in boxes:
        if any(_inside(b, r, 1.0) for r in runs):
            continue  # a cell of a character run
        if any(
            _iou(b, t) > 0.8 or _inside(b, t, 0.5) and _area(t) < 1.2 * _area(b)
            for t in taken
        ):
            continue
        words = pg.words_in(b)
        real = [i for i in words if not pg.is_placeholder(i)]
        placeholder = (
            " ".join(pg.words[i]["text"] for i in words if pg.is_placeholder(i)) or None
        )
        text = pg.text(real).lower()
        w, h = _w(b), _h(b)
        if (
            CHECKBOX_MIN <= w <= CHECKBOX_MAX
            and CHECKBOX_MIN <= h <= CHECKBOX_MAX
            and abs(w - h) <= 3
            and not real
        ):
            pg.add("checkbox", b, words, source="box")
        elif h > SLOT_MAX_HEIGHT:
            if any(k in text for k in PHOTO_WORDS):
                pg.add("photo_box", b, words)
            elif any(k in text for k in THUMB_WORDS) and len(real) <= 4:
                pg.add("thumbprint_box", b, words)
            elif not real or len(real) <= 3:
                pg.add("area", b, words)
            else:
                continue
        elif w >= SLOT_MIN_WIDTH and not real:
            pg.add("answer_slot", b, words, slot="box", placeholder=placeholder)
            slots.append(b)
        else:
            continue
        pg.used_words.update(words)
        taken.append(b)
    return slots


def _tables(pg: _Page, tables: List[dict]) -> List[Box]:
    boxes = []
    for t in tables:
        rows = t["rows"]
        grid = []
        for row in rows:
            grid.append([pg.text(pg.words_in(tuple(c))) if c else None for c in row])
        header = next((r for r in grid if any(r)), [])
        label_column = [r[0] for r in grid[1:] if r and r[0]]
        empty = sum(1 for r in grid[1:] for c in r[1:] if c == "")
        words = pg.words_in(t["box"])
        pg.add(
            "table",
            t["box"],
            words,
            rows=len(rows),
            cols=max(len(r) for r in rows),
            header=header,
            row_labels=label_column,
            empty_cells=empty,
            cells=[[_r(tuple(c)) if c else None for c in row] for row in rows],
        )
        pg.used_words.update(words)
        boxes.append(t["box"])
    return boxes


def _underlines(pg: _Page, frames: List[Box]):
    candidates = [
        _box(l)
        for l in pg.page.lines
        if abs(float(l["top"]) - float(l["bottom"])) < 1.0
    ]
    candidates += [r["box"] for r in _rects(pg) if _h(r["box"]) <= 1.5]
    for b in candidates:
        if _w(b) < UNDERLINE_MIN_WIDTH:
            continue
        y = b[1]
        if any(_inside(b, f, 1.0) for f in frames if _h(f) > 5):
            continue  # a rule inside a table or box, not an answer line
        on_frame = any(
            abs(y - f[1]) <= 1.5 or abs(y - f[3]) <= 1.5
            for f in frames
            if f[0] - 2 <= b[0] and b[2] <= f[2] + 2
        )
        if on_frame:
            continue
        above = (b[0], y - 12, b[2], y - 0.5)
        if [i for i in pg.words_in(above, pad=0) if not pg.is_placeholder(i)]:
            continue
        pg.add("answer_slot", b, [], slot="underline")


def _leader_dots(pg: _Page):
    for i, word in enumerate(pg.words):
        text = word["text"]
        b = pg.boxes[i]
        if _DOTS.match(text):
            pg.add("answer_slot", b, [i], slot="dots")
            pg.used_words.add(i)
            continue
        for pattern, dots_first in ((_TRAILING_DOTS, False), (_LEADING_DOTS, True)):
            m = pattern.match(text)
            if (
                m
                and m.group(1 if dots_first else 2)
                and m.group(2 if dots_first else 1).strip()
            ):
                dots = m.group(1 if dots_first else 2)
                share = len(dots) / len(text)
                width = _w(b) * share
                box = (
                    (b[0], b[1], b[0] + width, b[3])
                    if dots_first
                    else (b[2] - width, b[1], b[2], b[3])
                )
                pg.add(
                    "answer_slot",
                    box,
                    [i],
                    slot="dots",
                    label_part=m.group(2 if dots_first else 1).strip(),
                )
                break


def _paren_and_glyph_checkboxes(pg: _Page):
    chars = sorted(
        (c for c in pg.page.dedupe_chars().chars if c.get("text")),
        key=lambda c: (round(float(c["top"])), float(c["x0"])),
    )
    for idx, ch in enumerate(chars):
        t = ch["text"]
        if t in BOX_GLYPHS:
            pg.add("checkbox", _box(ch), pg.words_in(_box(ch)), source="glyph")
        elif t in TICK_GLYPHS:
            pg.add("tick", _box(ch), pg.words_in(_box(ch)))
        elif t == "(":
            for nxt in chars[idx + 1 : idx + 9]:
                if abs(float(nxt["top"]) - float(ch["top"])) > 2:
                    break
                if nxt["text"] == ")" and float(nxt["x0"]) - float(ch["x1"]) <= 14:
                    pg.add(
                        "checkbox", _union([_box(ch), _box(nxt)]), [], source="parens"
                    )
                    break
                if nxt["text"].strip():
                    break


def _signatures(pg: _Page, slots: List[dict]):
    for line in _lines(pg):
        text = " ".join(pg.words[i]["text"] for i in line).lower()
        if not any(k in text for k in SIGNATURE_WORDS):
            continue
        box = _union([pg.boxes[i] for i in line])
        candidates = [s for s in slots if s["kind"] == "answer_slot"]
        same_line = [
            s
            for s in candidates
            if abs(s["bbox"][1] - box[1]) <= 3
            and s["bbox"][0] - 40 <= box[2]
            and s["bbox"][2] + 40 >= box[0]
        ]
        above = [
            s
            for s in candidates
            if 0 <= box[1] - s["bbox"][3] <= 30
            and s["bbox"][0] - 40 <= box[2]
            and s["bbox"][2] + 40 >= box[0]
        ]
        near = same_line or sorted(above, key=lambda s: box[1] - s["bbox"][3])
        thumb = any(k in text for k in ("thumb", "औंठा"))
        pg.add(
            "signature",
            box,
            line,
            label=" ".join(pg.words[i]["text"] for i in line),
            slot=near[0]["id"] if near else None,
            thumbprint=thumb,
        )


def _column_end(pg: _Page, region: Box, start: float) -> float:
    """Where the fields under a side-column heading end: at the first line with
    content left of the column, or after a vertical gap."""
    x0 = region[0]
    items = [pg.boxes[i] for i in range(len(pg.words))] + [
        tuple(p["bbox"])
        for p in pg.primitives
        if p["kind"] in ("answer_slot", "cell_run", "checkbox")
    ]
    items = sorted(
        (b for b in items if b[1] >= start - 1 and b[3] <= region[3] + 1),
        key=lambda b: b[1],
    )
    bottom = start
    for b in items:
        if b[1] - bottom > 18:
            break
        if b[0] < x0 - 5 and b[2] > x0 - 5:
            continue  # spans the column edge: a frame line, not a field
        if b[2] <= x0 - 5:
            break  # content in the main column: the side block has ended
        bottom = max(bottom, b[3])
    return bottom + 2


def _staff_regions(pg: _Page, bars: List[dict], frames_all: Sequence[Box] = ()):
    lines = _lines(pg)
    for line in lines:
        text = " ".join(pg.words[i]["text"] for i in line).lower().replace("’", "'")
        if not any(p in text for p in STAFF_PHRASES):
            continue
        box = _union([pg.boxes[i] for i in line])
        container = next(
            (b for b in bars if _centre_inside(box, tuple(b["bbox"]))), None
        )
        top = container["bbox"][1] if container else box[1]
        below = sorted(b["bbox"][1] for b in bars if b["bbox"][1] > top + 2)
        bottom = below[0] if below else pg.height
        x0, x1 = (
            (container["bbox"][0], container["bbox"][2])
            if container
            else (0.0, pg.width)
        )
        # a frame drawn around the heading and its fields bounds the region better
        frames = [
            f
            for f in frames_all
            if _inside(box, f, 2) and f[3] > box[3] + 5 and _w(f) >= _w(box)
        ]
        if frames:
            frame = min(frames, key=_area)
            x0, top, x1 = min(x0, frame[0]), min(top, frame[1]), max(x1, frame[2])
            bottom = min(bottom, frame[3]) if bottom > frame[1] else frame[3]
        if container and x0 > 0.2 * pg.width:
            bottom = min(bottom, _column_end(pg, (x0, top, x1, bottom), box[3]))
        region = (x0, top, x1, bottom)
        pg.add(
            "staff_region",
            region,
            pg.words_in(region),
            heading=" ".join(pg.words[i]["text"] for i in line),
        )


def _images(pg: _Page):
    page_area = pg.width * pg.height
    for image in pg.page.images:
        b = _box(image)
        share = _area(b) / page_area if page_area else 0
        if share >= 0.2:
            pg.add(
                "watermark" if pg.page.chars else "image", b, [], share=round(share, 3)
            )
        elif b[1] < pg.height * 0.25:
            pg.add("logo", b, [], share=round(share, 3))
        else:
            pg.add("image", b, [], share=round(share, 3))


def _lines(pg: _Page) -> List[List[int]]:
    order = sorted(range(len(pg.words)), key=lambda i: (pg.boxes[i][1], pg.boxes[i][0]))
    lines: List[List[int]] = []
    for i in order:
        if lines and abs(pg.boxes[lines[-1][0]][1] - pg.boxes[i][1]) <= 2.0:
            lines[-1].append(i)
        else:
            lines.append([i])
    return [sorted(line, key=lambda i: pg.boxes[i][0]) for line in lines]


def _paragraphs(pg: _Page):
    taken = [
        tuple(p["bbox"])
        for p in pg.primitives
        if p["kind"]
        in (
            "table",
            "section_bar",
            "answer_slot",
            "cell_run",
            "checkbox",
            "area",
            "staff_region",
        )
    ]
    interactive = [
        tuple(p["bbox"])
        for p in pg.primitives
        if p["kind"] in ("answer_slot", "cell_run", "checkbox", "tick")
    ]
    block: List[List[int]] = []

    def flush():
        words = [i for line in block for i in line]
        if len(words) >= PARAGRAPH_MIN_WORDS:
            box = _union([pg.boxes[i] for i in words])
            if not any(_iou(box, t) > 0.3 for t in taken):
                pg.add("paragraph", box, words, word_count=len(words))

    def prose(line, box) -> bool:
        if len(line) < 5 or _w(box) < 0.35 * pg.width:
            return False
        # a line holding a slot or a checkbox is a question row, not prose
        return not any(_iou(box, t) > 0 or _inside(t, box, 2) for t in interactive)

    previous = None
    for line in _lines(pg):
        box = _union([pg.boxes[i] for i in line])
        height = _h(box) or 10
        if not prose(line, box):
            flush()
            block, previous = [], box
            continue
        if previous is not None and block and box[1] - previous[3] <= 0.8 * height:
            block.append(line)
        else:
            flush()
            block = [line]
        previous = box
    flush()


def page_layout(page, words: Optional[List[dict]] = None) -> dict:
    words = words if words is not None else page_words(page)["words"]
    pg = _Page(page, words)
    rects = _rects(pg)
    grid_boxes, tables = _grid_cells(pg)
    table_frames = [t["box"] for t in tables]
    bars = _section_bars(pg, rects, exclude=table_frames)
    table_boxes = _tables(pg, tables)
    bar_boxes = [tuple(b["bbox"]) for b in bars]
    candidate_boxes = [
        r["box"] for r in rects if tuple(r["box"]) not in bar_boxes
    ] + grid_boxes
    # drop boxes that are the cells of a detected table
    candidate_boxes = _dedupe(
        [b for b in candidate_boxes if not any(_inside(b, t) for t in table_boxes)]
    )
    _cell_runs(pg, candidate_boxes)
    run_boxes = [tuple(p["bbox"]) for p in pg.primitives if p["kind"] == "cell_run"]
    frames: List[Box] = list(table_boxes) + run_boxes + bar_boxes
    _classify_boxes(pg, candidate_boxes, list(frames), run_boxes)
    frames += [tuple(p["bbox"]) for p in pg.primitives]
    _underlines(pg, frames)
    _leader_dots(pg)
    _paren_and_glyph_checkboxes(pg)
    _signatures(pg, pg.primitives)
    outlines = [r["box"] for r in _all_outlines(pg)]
    _staff_regions(pg, bars, outlines + list(table_boxes))
    _images(pg)
    _paragraphs(pg)
    counts: Dict[str, int] = {}
    for p in pg.primitives:
        counts[p["kind"]] = counts.get(p["kind"], 0) + 1
    placeholders = [i for i in range(len(words)) if pg.is_placeholder(i)]
    return {
        "primitives": pg.primitives,
        "counts": counts,
        "placeholder_words": placeholders,
    }


def extract_layout(data: bytes, skip_pages: Optional[set] = None) -> dict:
    import pdfplumber

    pages = []
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for index, page in enumerate(pdf.pages):
            number = index + 1
            if skip_pages and number in skip_pages:
                pages.append(
                    {"number": number, "skipped": True, "primitives": [], "counts": {}}
                )
                continue
            pages.append({"number": number, "skipped": False, **page_layout(page)})
    return {"pages": pages}
