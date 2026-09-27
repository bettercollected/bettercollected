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


def _font(name: str) -> bytes:
    """A simple font with widths and a descriptor, as real documents carry."""
    widths = b" ".join([b"500"] * 224)
    return (
        b"<< /Type /Font /Subtype /Type1 /BaseFont /"
        + name.encode()
        + b" /FirstChar 32 /LastChar 255 /Widths ["
        + widths
        + b"]"
        + b" /FontDescriptor << /Type /FontDescriptor /FontName /"
        + name.encode()
        + b" /Flags 32 /FontBBox [0 -200 1000 800] /ItalicAngle 0 /Ascent 800"
        + b" /Descent -200 /CapHeight 700 /StemV 80 >> >>"
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
        _font(font),
    ]
    for p in page_ids:
        objects.append(
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 3 0 R >> >> /Contents "
            + str(p + 1).encode()
            + b" 0 R >>"
        )
        objects.append(_stream(content))
    return _pdf(objects)


def many_fonts_pdf(names) -> bytes:
    """One line per font, each font a separate resource (attacker-chosen names)."""
    resources = b" ".join(f"/F{i} {3 + i} 0 R".encode() for i in range(len(names)))
    text = b"".join(
        f"BT /F{i} 10 Tf 72 {800 - 12 * i} Td (kl/ro) Tj ET\n".encode()
        for i in range(len(names))
    )
    page = 3 + len(names)
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        f"<< /Type /Pages /Kids [{page} 0 R] /Count 1 >>".encode(),
    ]
    objects += [_font(name) for name in names]
    objects.append(
        f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << ".encode()
        + resources
        + f" >> >> /Contents {page + 1} 0 R >>".encode()
    )
    objects.append(_stream(text))
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


def form_pdf(filled: bool = False) -> bytes:
    """A vector form with one of each layout element (coordinates: PDF points,
    origin bottom-left; 595 x 842 page). ``filled`` writes answers into it in
    another font, as a typed-in and flattened form would have."""

    def text(x, y, s, size=11, font="F1", grey=None, white=False):
        colour = (
            b"1 1 1 rg "
            if white
            else (f"{grey} g ".encode() if grey is not None else b"0 g ")
        )
        return (
            colour
            + f"BT /{font} {size} Tf {x} {y} Td (".encode()
            + s.encode("latin-1")
            + b") Tj ET 0 g\n"
        )

    ops = []
    # section bar with a white heading
    ops.append(b"1 0 0 rg 50 780 495 18 re f 0 g\n")
    ops.append(text(56, 785, "Personal details", 12, "F2", white=True))
    # text answer box
    ops.append(text(56, 750, "Full name"))
    ops.append(b"150 745 280 18 re S\n")
    # date boxes with grey placeholders
    ops.append(text(56, 720, "Date of birth"))
    ops.append(b"150 715 30 18 re S 184 715 30 18 re S 218 715 50 18 re S\n")
    ops.append(
        text(156, 720, "DD", grey=0.75)
        + text(190, 720, "MM", grey=0.75)
        + text(226, 720, "YYYY", grey=0.75)
    )
    # ten character cells
    ops.append(text(56, 690, "Account number"))
    ops.append(
        b"".join(f"{150 + 14 * i} 685 14 18 re S ".encode() for i in range(10)) + b"\n"
    )
    # square checkboxes and parenthesis checkboxes
    ops.append(text(56, 662, "Gender"))
    ops.append(b"150 660 12 12 re S 230 660 12 12 re S\n")
    ops.append(text(166, 662, "Male") + text(246, 662, "Female"))
    ops.append(text(56, 640, "Married?    (    ) Yes    (    ) No"))
    # an underline answer and leader dots
    ops.append(text(56, 612, "Remarks"))
    ops.append(b"150 610 m 400 610 l S\n")
    ops.append(text(56, 585, "Signature ..........................."))
    # photo frame
    ops.append(b"450 620 90 110 re S\n")
    ops.append(text(475, 670, "Photo"))
    # a data table: header + two empty rows, ruled with lines
    for y in (560, 540, 520, 500):
        ops.append(f"56 {y} m 500 {y} l S\n".encode())
    for x in (56, 200, 350, 500):
        ops.append(f"{x} 500 m {x} 560 l S\n".encode())
    ops.append(
        text(62, 546, "Name") + text(206, 546, "Relation") + text(356, 546, "Account")
    )
    # a paragraph of running text
    sentence = "I declare that the information given in this form is true and complete to my knowledge"
    for i in range(4):
        ops.append(text(56, 440 - 13 * i, sentence, 10))
    # a staff-only band and its field
    ops.append(b"0.2 g 50 330 495 16 re f 0 g\n")
    ops.append(text(56, 334, "For office use only", 11, "F2", white=True))
    ops.append(text(56, 305, "Reviewed by"))
    ops.append(b"150 300 200 18 re S\n")

    if filled:
        ops.append(text(156, 750, "Asha Kumari Rai", 10, "F3"))
        ops.append(text(156, 614, "Moving abroad soon", 10, "F3"))
        ops.append(text(206, 526, "Brother", 10, "F3"))

    content = b"".join(ops)
    return _pdf(
        [
            b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [5 0 R] /Count 1 >>",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 3 0 R /F2 4 0 R /F3 7 0 R >> >> /Contents 6 0 R >>",
            _stream(content),
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>",
        ]
    )
