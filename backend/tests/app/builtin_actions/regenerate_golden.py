"""Make ``golden/qa.json`` from the actions executor's own ``utilities/form.py``.

    cd backend && uv run python -m tests.app.builtin_actions.regenerate_golden

The executor's file only needs the standard library, so it is loaded by path.
Run this only on purpose: the golden file is what the built-in actions sent
before they moved to the backend, and receivers parse it. A changed golden file
is a changed receiver contract and belongs in the changelog.
"""

import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
EXECUTOR_FORM = REPO / "temporal" / "actions-executor" / "utilities" / "form.py"
GOLDEN = HERE / "golden" / "qa.json"


def load_executor_form():
    spec = importlib.util.spec_from_file_location("executor_utilities_form", EXECUTOR_FORM)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    from tests.app.builtin_actions import battery

    if not EXECUTOR_FORM.exists():
        print(f"{EXECUTOR_FORM} is gone: the golden file is the only record now")
        return 1
    result = battery.run(load_executor_form())
    GOLDEN.parent.mkdir(exist_ok=True)
    GOLDEN.write_text(
        json.dumps(result, ensure_ascii=False, indent=1, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {GOLDEN.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
