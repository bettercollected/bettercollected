"""The committed models match docs/spec and docs/api (regenerate with
``uv run python scripts/generate.py``)."""

import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent


def test_models_are_current(tmp_path):
    spec = importlib.util.spec_from_file_location(
        "generate", HERE / "scripts" / "generate.py"
    )
    generate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(generate)
    generate.MODELS = tmp_path
    generate.main()
    for name in ("spec.py", "api.py"):
        committed = (HERE / "src" / "bettercollected" / "models" / name).read_text()
        assert (
            tmp_path / name
        ).read_text() == committed, (
            f"models/{name} is stale: run uv run python scripts/generate.py"
        )
