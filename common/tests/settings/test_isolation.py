"""``common.settings`` stays a pure library: no backend, no crypto_service, no
SQLAlchemy, no FastAPI, no database drivers."""

import ast
import os
import subprocess
import sys
from pathlib import Path

import common.settings

PACKAGE = Path(common.settings.__file__).parent
FORBIDDEN = (
    "backend",
    "auth",
    "common.services",
    "common.models",
    "common.db",
    "common.base",
    "common.configs",
    "sqlalchemy",
    "fastapi",
    "starlette",
    "beanie",
    "motor",
    "pymongo",
    "asyncpg",
    "psycopg",
    "alembic",
    "tink",
)


def _imports(path: Path):
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name
        elif isinstance(node, ast.ImportFrom):
            if node.level:  # relative: stays inside the package
                continue
            base = node.module or ""
            yield base
            for alias in node.names:
                yield f"{base}.{alias.name}"


def _hits(name: str) -> bool:
    return any(name == bad or name.startswith(bad + ".") for bad in FORBIDDEN)


def test_no_module_imports_a_forbidden_package():
    files = list(PACKAGE.rglob("*.py"))
    assert len(files) >= 10
    offenders = {
        f"{p.relative_to(PACKAGE)}: {name}"
        for p in files
        for name in _imports(p)
        if _hits(name)
    }
    assert not offenders


def test_the_scan_catches_forbidden_imports(tmp_path):
    bad = tmp_path / "x.py"
    bad.write_text(
        "from common.services import crypto_service\nimport sqlalchemy\n"
        "from backend.admin import config\nfrom fastapi import FastAPI\n"
    )
    assert {n for n in _imports(bad) if _hits(n)} >= {
        "common.services.crypto_service",
        "sqlalchemy",
        "backend.admin.config",
        "fastapi",
    }


def test_importing_it_loads_none_of_them():
    code = (
        "import sys\n"
        "import common.settings, common.settings.registry, common.settings.canonical\n"
        "import common.settings.signing, common.settings.keys, common.settings.snapshot\n"
        "import common.settings.resolve, common.settings.crypto.envelope\n"
        f"forbidden = {FORBIDDEN!r}\n"
        "bad = sorted(m for m in sys.modules if any(m == b or m.startswith(b + '.')"
        " for b in forbidden))\n"
        "print('OFFENDERS=' + ','.join(bad))\n"
    )
    env = {
        k: v
        for k, v in os.environ.items()
        if k not in {"MASTER_ENCRYPTION_KEYSET", "SETTINGS_MASTER_KEY"}
    }
    done = subprocess.run(
        [sys.executable, "-I", "-c", code],
        cwd=PACKAGE.parents[1],
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert done.returncode == 0, done.stderr[-2000:]
    assert done.stdout.strip().splitlines()[-1] == "OFFENDERS="
