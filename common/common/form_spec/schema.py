"""The committed JSON Schema of the form spec, generated from the models.

Regenerate after changing ``common/form_spec/models.py`` (from ``common/``)::

    uv run python -m common.form_spec.schema

``--check`` exits non-zero when the committed file is stale (the test suite
runs the same comparison).
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict

from common.form_spec.models import SCHEMA_ID, FormSpec

# <repo>/common/common/form_spec/schema.py -> <repo>/docs/spec/...
SCHEMA_PATH = (
    Path(__file__).resolve().parents[3] / "docs" / "spec" / "form-spec-v1.schema.json"
)


def build_schema() -> Dict[str, Any]:
    schema = FormSpec.model_json_schema(by_alias=True, mode="validation")
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": SCHEMA_ID,
        **schema,
    }


def render_schema() -> str:
    return json.dumps(build_schema(), indent=2, ensure_ascii=False) + "\n"


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    rendered = render_schema()
    if "--check" in argv:
        current = SCHEMA_PATH.read_text() if SCHEMA_PATH.exists() else ""
        if current != rendered:
            print(f"{SCHEMA_PATH} is stale: run python -m common.form_spec.schema")
            return 1
        return 0
    SCHEMA_PATH.parent.mkdir(parents=True, exist_ok=True)
    SCHEMA_PATH.write_text(rendered)
    print(f"Wrote {SCHEMA_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
