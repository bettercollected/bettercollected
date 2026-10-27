"""Import of forms exported from Open Formulieren (docs/open-formulieren.md).

The uploaded archive is untrusted data: ``archive`` reads it with hard limits
and returns plain JSON values, ``importer`` maps those to a draft form through
the form edit operations, and nothing in the file is ever executed, evaluated
or rendered. ``mapping`` holds the tables of the format (kept together so an
export can use them in reverse).
"""
