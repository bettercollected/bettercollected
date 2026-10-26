"""Beanie is a test-only dependency: no service imports it, and none declares
it (or Motor, or mongomock) among its runtime dependencies. The application
reads and writes Postgres only; Mongo is read, with pymongo, by the import
from 4.0 (``python -m <service>.migrate``) alone."""

import re
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

#: the packages that ship in an image
RUNTIME_PACKAGES = [
    "backend/backend",
    "backend/scripts",
    "auth/auth",
    "integrations/google/googleform",
    "common/common",
    "temporal",
]
#: test support kept in the ``common`` package: the 4.0 codec and classes the
#: golden fixtures and the import tests compare the record layer with
TEST_SUPPORT = {
    "common/common/db/beanie_bridge.py",
    "common/common/records/golden.py",
}
IMPORT = re.compile(r"^\s*(?:from|import)\s+(beanie|motor|mongomock)\b", re.M)
PYPROJECTS = [
    "common/pyproject.toml",
    "backend/pyproject.toml",
    "auth/pyproject.toml",
    "integrations/google/pyproject.toml",
]


def test_no_runtime_module_imports_beanie():
    found = []
    for package in RUNTIME_PACKAGES:
        for path in sorted((ROOT / package).rglob("*.py")):
            relative = path.relative_to(ROOT).as_posix()
            if relative in TEST_SUPPORT or "/tests/" in relative:
                continue
            if IMPORT.search(path.read_text(encoding="utf-8")):
                found.append(relative)
    assert found == []


@pytest.mark.parametrize("pyproject", PYPROJECTS)
def test_beanie_is_not_a_runtime_dependency(pyproject):
    project = tomllib.loads((ROOT / pyproject).read_text(encoding="utf-8"))
    runtime = " ".join(project["project"]["dependencies"]).lower()
    assert not re.search(r"\b(beanie|motor|mongomock)\b", runtime)
    # the import from 4.0 reads Mongo with pymongo, which common declares
    if pyproject == "common/pyproject.toml":
        assert "pymongo" in runtime
