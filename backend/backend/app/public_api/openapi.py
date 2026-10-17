"""The committed OpenAPI document of the public API.

Regenerate after changing an endpoint or its models (from ``backend/``, with
the backend's environment)::

    uv run python -m backend.app.public_api.openapi

``--check`` exits non-zero when the committed file is stale (the test suite
runs the same comparison). The SDKs in ``sdk/`` are generated from it.
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict

# <repo>/backend/backend/app/public_api/openapi.py -> <repo>/docs/api/...
OPENAPI_PATH = (
    Path(__file__).resolve().parents[4] / "docs" / "api" / "public-v1.openapi.json"
)


def build_openapi() -> Dict[str, Any]:
    from backend.app.public_api.app import build_public_api

    return build_public_api().openapi()


def render_openapi() -> str:
    return json.dumps(build_openapi(), indent=2, ensure_ascii=False) + "\n"


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    rendered = render_openapi()
    if "--check" in argv:
        current = OPENAPI_PATH.read_text() if OPENAPI_PATH.exists() else ""
        if current != rendered:
            print(
                f"{OPENAPI_PATH} is stale: run python -m backend.app.public_api.openapi"
            )
            return 1
        return 0
    OPENAPI_PATH.parent.mkdir(parents=True, exist_ok=True)
    OPENAPI_PATH.write_text(rendered)
    print(f"Wrote {OPENAPI_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
