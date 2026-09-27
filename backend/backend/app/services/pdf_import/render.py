"""Render pages to PNG for the image-reading stages.

Native code (pdfium for PDFs, Pillow's decoders for photos) parses the
document here, so this only ever runs in the isolated sandbox container (#703),
never in a local child.

Import-safe for the sandbox child: no imports from the backend package.
"""

from __future__ import annotations

import base64
import io
from typing import Iterable, List


def _png(image, max_side: int) -> dict:
    from PIL import Image

    image = image.convert("RGB")
    width, height = image.size
    scale = min(1.0, max_side / float(max(width, height)))
    if scale < 1.0:
        image = image.resize(
            (max(1, int(width * scale)), max(1, int(height * scale))), Image.LANCZOS
        )
    out = io.BytesIO()
    image.save(out, format="PNG", optimize=True)
    return {
        "width_px": image.size[0],
        "height_px": image.size[1],
        "png": base64.b64encode(out.getvalue()).decode("ascii"),
    }


def render_pdf(data: bytes, pages: Iterable[int], max_side: int) -> dict:
    import pypdfium2 as pdfium

    doc = pdfium.PdfDocument(data)
    try:
        out: List[dict] = []
        for number in pages:
            if not 1 <= number <= len(doc):
                continue
            page = doc[number - 1]
            width, height = page.get_size()
            scale = max_side / float(max(width, height))  # points -> pixels
            bitmap = page.render(scale=scale)
            out.append({"number": number, **_png(bitmap.to_pil(), max_side)})
            page.close()
        return {"pages": out}
    finally:
        doc.close()


def render_image(data: bytes, max_side: int, max_pixels: int) -> dict:
    from PIL import Image, ImageOps

    Image.MAX_IMAGE_PIXELS = max_pixels
    with Image.open(io.BytesIO(data)) as image:
        # Pillow only raises at twice MAX_IMAGE_PIXELS: check the header's size
        # before anything decodes the pixels
        width, height = image.size
        if width * height > max_pixels:
            from .analysis import DocumentRefused

            raise DocumentRefused("too_large", "This image is too large to import.")
        image = ImageOps.exif_transpose(
            image
        )  # phone photos carry their rotation in EXIF
        return {"pages": [{"number": 1, **_png(image, max_side)}]}
