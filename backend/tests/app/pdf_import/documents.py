"""Synthetic documents for the import tests, generated here (no sample files)."""

import io
from typing import List, Optional


def _pdf(objects: List[bytes], root: int = 1) -> bytes:
    out = io.BytesIO()
    out.write(b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(out.tell())
        out.write(f"{number} 0 obj\n".encode() + body + b"\nendobj\n")
    xref = out.tell()
    out.write(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    for offset in offsets:
        out.write(f"{offset:010d} 00000 n \n".encode())
    out.write(
        f"trailer\n<< /Size {len(objects) + 1} /Root {root} 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    )
    return out.getvalue()


def _stream(content: bytes) -> bytes:
    return (
        b"<< /Length "
        + str(len(content)).encode()
        + b" >>\nstream\n"
        + content
        + b"\nendstream"
    )


def text_pdf(
    lines: Optional[List[str]] = None, font: str = "Helvetica", pages: int = 1
) -> bytes:
    """A vector form: text lines and one answer box per page, in ``font``."""
    lines = lines or ["Application form", "Full name", "Email address"]
    text = b"".join(
        b"BT /F1 12 Tf 72 "
        + str(720 - 30 * i).encode()
        + b" Td ("
        + line.encode("latin-1")
        + b") Tj ET\n"
        for i, line in enumerate(lines)
    )
    content = text + b"200 640 250 20 re S\n"
    page_ids = [4 + 2 * i for i in range(pages)]
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids ["
        + b" ".join(f"{p} 0 R".encode() for p in page_ids)
        + b"] /Count "
        + str(pages).encode()
        + b" >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /" + font.encode() + b" >>",
    ]
    for p in page_ids:
        objects.append(
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 3 0 R >> >> /Contents "
            + str(p + 1).encode()
            + b" 0 R >>"
        )
        objects.append(_stream(content))
    return _pdf(objects)


def fillable_pdf() -> bytes:
    """One page with a label and a text field widget (AcroForm)."""
    content = b"BT /F1 12 Tf 72 720 Td (Full name) Tj ET\n"
    return _pdf(
        [
            b"<< /Type /Catalog /Pages 2 0 R /AcroForm << /Fields [6 0 R] >> >>",
            b"<< /Type /Pages /Kids [4 0 R] /Count 1 >>",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 3 0 R >> >> /Contents 5 0 R /Annots [6 0 R] >>",
            _stream(content),
            b"<< /Type /Annot /Subtype /Widget /FT /Tx /T (full_name) /TU (Full name) /Rect [200 710 450 730] /P 4 0 R >>",
        ]
    )


def scan_pdf() -> bytes:
    """A page that is only an image, like a scanned paper form."""
    from PIL import Image, ImageDraw

    image = Image.new("RGB", (1240, 1754), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle([100, 100, 1100, 180], outline="black", width=3)
    draw.text((110, 120), "Name", fill="black")
    out = io.BytesIO()
    image.save(out, format="PDF", resolution=150)
    return out.getvalue()


def photo_png() -> bytes:
    from PIL import Image

    out = io.BytesIO()
    Image.new("RGB", (800, 1100), "white").save(out, format="PNG")
    return out.getvalue()


def encrypted_pdf() -> bytes:
    from pypdf import PdfReader, PdfWriter

    writer = PdfWriter()
    for page in PdfReader(io.BytesIO(text_pdf())).pages:
        writer.add_page(page)
    writer.encrypt(user_password="secret", owner_password="owner")
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()
