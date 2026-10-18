"""The security primitives stay a leaf: no application wiring, no shared
crypto service (which refuses to import without a keyset)."""

import ast
import subprocess
import sys
from pathlib import Path

import pytest

SECURITY = Path(__file__).resolve().parents[2] / "backend" / "admin" / "security"
FILES = sorted(p for p in SECURITY.glob("*.py") if p.name != "keys.py")
FORBIDDEN = (
    "backend.app.router",
    "backend.app.container",
    "backend.app.controllers",
    "common.services.crypto_service",
)
# imported names that would pull the public application in via its package
FORBIDDEN_PREFIXES = ("backend.app",)


def imported_modules(path: Path):
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name
        elif isinstance(node, ast.ImportFrom) and node.module:
            yield node.module
            for alias in node.names:
                yield f"{node.module}.{alias.name}"


def test_there_are_files_to_check():
    assert {"totp.py", "envelope.py", "recovery.py", "csrf.py"} <= {
        p.name for p in FILES
    }


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.name)
def test_no_forbidden_imports(path):
    for module in imported_modules(path):
        assert not module.startswith(FORBIDDEN_PREFIXES), (path.name, module)
        assert not module.startswith(FORBIDDEN), (path.name, module)
        assert not module.startswith("common.services"), (path.name, module)


def test_importing_the_primitives_loads_no_application():
    code = (
        "import sys\n"
        "import backend.admin.security.totp, backend.admin.security.envelope\n"
        "import backend.admin.security.recovery, backend.admin.security.csrf\n"
        "import backend.admin.security.clock, backend.admin.security.ratelimit\n"
        "import backend.admin.security.mailer\n"
        "bad = [m for m in sys.modules if m in ('backend.app', 'backend.app.router',"
        " 'backend.app.container') or m.startswith('common.services.crypto')]\n"
        "assert not bad, bad\n"
    )
    result = subprocess.run(
        [sys.executable, "-I", "-c", code], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr[-500:]
