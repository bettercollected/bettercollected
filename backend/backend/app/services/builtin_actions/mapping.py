"""Which questions a built-in action sends when it sends "every question".

A webhook or an email action that replaced a built-in action sent every question
of the form, new ones included. Those actions carry ``all_questions`` and this
mapping is worked out from the form at send time, so it follows the form."""

from __future__ import annotations

import re
from typing import Any, Collection, List, Tuple

from backend.app.services.registration import body as body_builder


def all_questions_mapping(
    form: Any, *, reserved: Collection[str] = ()
) -> List[Tuple[str, str]]:
    """``(source, key)`` for every question of ``form`` that can be sent:
    supported, no file, no item of a repeating group on its own (the group is one
    value), no internal field (the form's variables never list one). A key is
    the question's id made of letters, digits and ``_``, made unique (``a``,
    ``a_2``...) and never one of ``reserved``; a question whose id cannot make a
    valid key is left out."""
    mapping: List[Tuple[str, str]] = []
    used = set(reserved)
    for variable in body_builder.mappable(form):
        if variable.type == "file_upload":
            continue
        base = re.sub(r"[^A-Za-z0-9_]", "_", variable.source)
        key, number = base, 1
        while key in used:
            number += 1
            key = f"{base}_{number}"
        if not body_builder.KEY_PATTERN.match(key):
            continue
        used.add(key)
        mapping.append((variable.source, key))
    return mapping
