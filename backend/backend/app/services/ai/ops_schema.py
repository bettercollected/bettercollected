"""The committed JSON Schema of the edit operations, generated from the
``FormOp`` union in ops.py.

Regenerate after changing the operations (from ``backend/``)::

    uv run python -m backend.app.services.ai.ops_schema

``--check`` exits non-zero when the committed file is stale (the test suite
runs the same comparison). Operations only the form editor may send carry
``"x-editorOnly": true`` and are listed in ``x-editorOnlyOps``.
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict

from backend.app.models.dtos.response_dtos import StandardFormFieldCamelModel
from backend.app.services.ai.ops import (
    EDITOR_FIELD_DEF,
    EDITOR_OP_TYPES,
    EDITOR_ONLY_OPS,
    FormOps,
)

SCHEMA_ID = (
    "https://raw.githubusercontent.com/bettercollected/bettercollected/"
    "develop/docs/spec/form-ops-v1.schema.json"
)
# <repo>/backend/backend/app/services/ai/ops_schema.py -> <repo>/docs/spec/...
SCHEMA_PATH = (
    Path(__file__).resolve().parents[5] / "docs" / "spec" / "form-ops-v1.schema.json"
)
REF_TEMPLATE = "#/$defs/{model}"


def build_schema() -> Dict[str, Any]:
    schema = FormOps.model_json_schema(
        by_alias=True, mode="validation", ref_template=REF_TEMPLATE
    )
    defs = schema.setdefault("$defs", {})
    field = StandardFormFieldCamelModel.model_json_schema(
        by_alias=True, mode="validation", ref_template=REF_TEMPLATE
    )
    for name, definition in field.pop("$defs", {}).items():
        defs.setdefault(name, definition)
    field["description"] = (
        "A question or page as the form editor holds it (camelCase), read "
        "and checked as a whole-form save reads it."
    )
    defs[EDITOR_FIELD_DEF] = field

    def point_at_field(value: Any) -> Any:
        if isinstance(value, dict):
            if value.get("x-editorField"):
                return {"$ref": REF_TEMPLATE.format(model=EDITOR_FIELD_DEF)}
            return {k: point_at_field(v) for k, v in value.items()}
        if isinstance(value, list):
            return [point_at_field(v) for v in value]
        return value

    schema = point_at_field(schema)
    defs = schema["$defs"]
    for op_type in EDITOR_OP_TYPES:
        defs[op_type.__name__]["x-editorOnly"] = True
    schema["title"] = "BetterCollected form edit operations v1"
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": SCHEMA_ID,
        "x-editorOnlyOps": sorted(EDITOR_ONLY_OPS),
        **schema,
        "$defs": dict(sorted(defs.items())),
    }


def render_schema() -> str:
    return json.dumps(build_schema(), indent=2, ensure_ascii=False) + "\n"


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    rendered = render_schema()
    if "--check" in argv:
        current = SCHEMA_PATH.read_text() if SCHEMA_PATH.exists() else ""
        if current != rendered:
            print(
                f"{SCHEMA_PATH} is stale: run "
                "python -m backend.app.services.ai.ops_schema"
            )
            return 1
        return 0
    SCHEMA_PATH.parent.mkdir(parents=True, exist_ok=True)
    SCHEMA_PATH.write_text(rendered)
    print(f"Wrote {SCHEMA_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
