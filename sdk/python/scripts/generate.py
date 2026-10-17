"""Regenerate the Pydantic models (run from sdk/python)::

    uv run python scripts/generate.py

- ``models/spec.py`` from the form spec JSON Schema (docs/spec);
- ``models/api.py`` from the public API's OpenAPI document (docs/api), its
  request and response bodies only: where they hold a spec document they
  take a plain object, which the client reads as ``spec.FormSpec``.
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
ROOT = HERE.parent.parent
SCHEMA = ROOT / "docs" / "spec" / "form-spec-v1.schema.json"
OPENAPI = ROOT / "docs" / "api" / "public-v1.openapi.json"
MODELS = HERE / "src" / "bettercollected" / "models"

COMMON = [
    "--output-model-type",
    "pydantic_v2.BaseModel",
    "--target-python-version",
    "3.10",
    "--use-standard-collections",
    "--use-union-operator",
    "--use-schema-description",
    "--field-constraints",
    "--snake-case-field",
    "--allow-population-by-field-name",
    "--disable-timestamp",
    "--use-double-quotes",
    "--enum-field-as-literal",
    "all",
    "--formatters",
    "black",
    "isort",
]


def codegen(source: Path, kind: str, target: Path, header: str, *extra: str) -> None:
    subprocess.run(
        [
            sys.executable,
            "-m",
            "datamodel_code_generator",
            "--input",
            str(source),
            "--input-file-type",
            kind,
            "--output",
            str(target),
            "--custom-file-header",
            header,
            *COMMON,
            *extra,
        ],
        check=True,
    )


def _reachable(schemas: dict, root: str) -> set:
    """``root`` and every schema it refers to, transitively."""
    seen, todo = set(), [root]
    while todo:
        name = todo.pop()
        if name in seen:
            continue
        seen.add(name)
        text = json.dumps(schemas[name])
        for part in text.split('"#/components/schemas/')[1:]:
            todo.append(part.split('"', 1)[0])
    return seen


def api_bodies() -> dict:
    """The OpenAPI document reduced to the API's own bodies; references to
    the spec's schemas become plain objects."""
    document = json.loads(OPENAPI.read_text())
    schemas = document["components"]["schemas"]
    spec_names = _reachable(schemas, "FormSpec")
    spec_object = {
        "type": "object",
        "additionalProperties": True,
        "description": "A form spec v1 document (bettercollected.models.spec.FormSpec).",
    }

    def replace(node):
        if isinstance(node, dict):
            ref = node.get("$ref", "")
            if ref.rsplit("/", 1)[-1] in spec_names and ref.startswith(
                "#/components/schemas/"
            ):
                return dict(spec_object)
            return {k: replace(v) for k, v in node.items()}
        if isinstance(node, list):
            return [replace(v) for v in node]
        return node

    used = set()
    for part in json.dumps(document["paths"]).split('"#/components/schemas/')[1:]:
        name = part.split('"', 1)[0]
        if name not in spec_names:
            used |= _reachable(schemas, name) - spec_names
    kept = {k: replace(v) for k, v in schemas.items() if k in used}
    return {
        "openapi": document["openapi"],
        "info": document["info"],
        "paths": {},
        "components": {"schemas": kept},
    }


def main() -> None:
    codegen(
        SCHEMA,
        "jsonschema",
        MODELS / "spec.py",
        "# Generated from docs/spec/form-spec-v1.schema.json by scripts/generate.py."
        " Do not edit.",
        "--class-name",
        "FormSpec",
    )
    with tempfile.TemporaryDirectory() as tmp:
        bodies = Path(tmp) / "bodies.json"
        bodies.write_text(json.dumps(api_bodies()))
        codegen(
            bodies,
            "openapi",
            MODELS / "api.py",
            "# Generated from docs/api/public-v1.openapi.json by scripts/generate.py."
            " Do not edit.",
        )
    print("Wrote models/spec.py and models/api.py")


if __name__ == "__main__":
    main()
