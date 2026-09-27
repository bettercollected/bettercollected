"""Page analysis: what is on each page and which route will read it.

Pure functions over an opened document; the sandbox calls them. Routes:

    widgets  the page has fillable (AcroForm) fields: read them exactly
    text     a trustworthy text layer over a vector drawing
    vision   a text layer that cannot be trusted as-is (legacy fonts, too
             little text for the drawing), read from the page image
    scan     the page is an image (a scan or a photographed form)
"""

from __future__ import annotations

import collections
import io
from dataclasses import asdict, dataclass, field
from typing import List

from .fonts import base_font_name, is_legacy_font
from .legacy_decode import decoder_for

# a page whose raster images cover more than this share, with little text, is a scan
SCAN_IMAGE_COVERAGE = 0.5
SCAN_MAX_CHARS = 40
# a page this share of whose characters are in legacy fonts is read from the image
LEGACY_SHARE_FOR_VISION = 0.2
# font names come from the document: bound what is stored on the record
MAX_FONTS_LISTED = 8
MAX_FONT_NAME = 64


class DocumentRefused(Exception):
    """The document cannot be imported; ``code`` is stable, ``message`` is for people."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class PageSignals:
    number: int
    width: float
    height: float
    chars: int = 0
    widgets: int = 0
    images: int = 0
    image_coverage: float = 0.0
    vector_objects: int = 0
    fonts: List[str] = field(default_factory=list)
    legacy_fonts: List[str] = field(default_factory=list)
    legacy_chars: int = 0
    route: str = "text"
    reasons: List[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        data = asdict(self)
        data.pop("legacy_chars")
        return data


def choose_route(page: PageSignals) -> PageSignals:
    reasons: List[str] = []
    if page.widgets:
        page.route = "widgets"
        reasons.append(f"{page.widgets} fillable fields")
    elif page.image_coverage >= SCAN_IMAGE_COVERAGE and page.chars <= SCAN_MAX_CHARS:
        page.route = "scan"
        reasons.append(
            f"images cover {page.image_coverage:.0%} of the page with no text layer"
        )
    elif page.chars and page.legacy_chars / page.chars >= LEGACY_SHARE_FOR_VISION:
        if page.legacy_fonts and all(decoder_for(f) for f in page.legacy_fonts):
            page.route = "text"
            reasons.append("legacy fonts decoded: " + ", ".join(page.legacy_fonts[:3]))
        else:
            page.route = "vision"
            reasons.append(
                "text set in legacy fonts: " + ", ".join(page.legacy_fonts[:3])
            )
    elif page.chars == 0 and page.vector_objects == 0 and page.images == 0:
        page.route = "text"
        reasons.append("blank page")
    elif page.chars == 0:
        page.route = "vision"
        reasons.append("drawing without a text layer")
    else:
        page.route = "text"
        reasons.append("text layer present")
    page.reasons = reasons
    return page


def analyze_pdf(data: bytes, max_pages: int) -> dict:
    """Signals and route for every page of a PDF. Raises DocumentRefused."""
    import pdfplumber
    from pypdf import PdfReader
    from pypdf.errors import FileNotDecryptedError, PdfReadError

    try:
        reader = PdfReader(io.BytesIO(data), strict=False)
        if reader.is_encrypted:
            # permission-only encryption opens with the empty password
            try:
                if not reader.decrypt(""):
                    raise FileNotDecryptedError("password required")
            except (FileNotDecryptedError, NotImplementedError):
                raise DocumentRefused(
                    "encrypted",
                    "This PDF is password-protected. Remove the password and upload it again.",
                )
        page_count = len(reader.pages)
    except DocumentRefused:
        raise
    except (PdfReadError, ValueError, KeyError, TypeError) as error:
        raise DocumentRefused(
            "unreadable", "This file could not be read as a PDF."
        ) from error
    if page_count == 0:
        raise DocumentRefused("empty", "This PDF has no pages.")
    if page_count > max_pages:
        raise DocumentRefused(
            "too_many_pages",
            f"This PDF has {page_count} pages; the limit is {max_pages} per import.",
        )

    widgets_per_page, resource_fonts = [], []
    for page in reader.pages:
        # base font names from the page resources: pdfminer reports "unknown" for
        # fonts without a descriptor, but the resource dictionary still names them
        names = set()
        try:
            fonts_dict = (page.get("/Resources") or {}).get("/Font") or {}
            for ref in fonts_dict.values():
                base = ref.get_object().get("/BaseFont")
                if base:
                    names.add(base_font_name(str(base).lstrip("/")))
        except Exception:  # noqa: BLE001 — a broken resource dictionary is skipped
            pass
        resource_fonts.append(names)
        annots = page.get("/Annots") or []
        count = 0
        for ref in annots:
            try:
                annot = ref.get_object()
            except Exception:  # noqa: BLE001 — a broken annotation is skipped
                continue
            if annot.get("/Subtype") == "/Widget":
                count += 1
        widgets_per_page.append(count)
    xfa = "/XFA" in (reader.trailer["/Root"].get("/AcroForm") or {})

    pages = []
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for index, page in enumerate(pdf.pages):
            area = float(page.width * page.height) or 1.0
            chars = [c for c in page.chars if not c.get("text", "").isspace()]
            fonts = collections.Counter(
                base_font_name(c.get("fontname", "")) for c in chars
            )
            legacy = {f for f in fonts if is_legacy_font(f)}
            page_resources = (
                resource_fonts[index] if index < len(resource_fonts) else set()
            )
            legacy_resources = {f for f in page_resources if is_legacy_font(f)}
            if legacy_resources and "unknown" in fonts:
                # characters pdfminer could not attribute belong to a legacy font on this page
                fonts[sorted(legacy_resources)[0]] += fonts.pop("unknown")
                legacy |= legacy_resources
            covered = 0.0
            for image in page.images:
                x0, x1 = max(0.0, image["x0"]), min(float(page.width), image["x1"])
                top, bottom = max(0.0, image["top"]), min(
                    float(page.height), image["bottom"]
                )
                covered += max(0.0, x1 - x0) * max(0.0, bottom - top)
            signals = PageSignals(
                number=index + 1,
                width=round(float(page.width), 1),
                height=round(float(page.height), 1),
                chars=len(chars),
                widgets=widgets_per_page[index] if index < len(widgets_per_page) else 0,
                images=len(page.images),
                image_coverage=round(min(1.0, covered / area), 3),
                vector_objects=len(page.lines) + len(page.rects) + len(page.curves),
                fonts=[
                    name[:MAX_FONT_NAME]
                    for name, _ in fonts.most_common(MAX_FONTS_LISTED)
                ],
                legacy_fonts=[
                    name[:MAX_FONT_NAME] for name in sorted(legacy)[:MAX_FONTS_LISTED]
                ],
                legacy_chars=sum(n for name, n in fonts.items() if name in legacy),
            )
            pages.append(choose_route(signals).as_dict())
    routes = collections.Counter(p["route"] for p in pages)
    return {
        "kind": "pdf",
        "page_count": page_count,
        "xfa": xfa,
        "routes": dict(routes),
        "pages": pages,
    }


def analyze_image(data: bytes, max_pixels: int) -> dict:
    """A photographed or scanned form uploaded as an image: one scan page."""
    from PIL import Image, UnidentifiedImageError

    Image.MAX_IMAGE_PIXELS = max_pixels
    try:
        with Image.open(io.BytesIO(data)) as image:
            image.verify()
        with Image.open(io.BytesIO(data)) as image:
            width, height = image.size
    except Image.DecompressionBombError as error:
        raise DocumentRefused(
            "too_large", "This image is too large to import."
        ) from error
    except (UnidentifiedImageError, OSError, SyntaxError) as error:
        raise DocumentRefused(
            "unreadable", "This file could not be read as an image."
        ) from error
    page = choose_route(
        PageSignals(
            number=1,
            width=float(width),
            height=float(height),
            images=1,
            image_coverage=1.0,
        )
    ).as_dict()
    return {
        "kind": "image",
        "page_count": 1,
        "xfa": False,
        "routes": {"scan": 1},
        "pages": [page],
    }
