"""``backend.admin`` stays independent of the public API and the response keyset."""

import ast
import os
import subprocess
import sys
from pathlib import Path

import backend.admin

PACKAGE = Path(backend.admin.__file__).parent
BACKEND_ROOT = PACKAGE.parents[1]
FORBIDDEN = (
    "backend.app.router",
    "backend.app.container",
    "backend.app.controllers",
    "common.services.crypto_service",
)


def _imports(path: Path):
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            yield base
            for alias in node.names:  # `from backend.app import router`
                yield f"{base}.{alias.name}"


def _hits(name: str) -> bool:
    return any(name == bad or name.startswith(bad + ".") for bad in FORBIDDEN)


def test_no_module_in_the_package_imports_forbidden_modules():
    files = list(PACKAGE.rglob("*.py"))
    assert len(files) > 8
    offenders = {
        f"{p.relative_to(PACKAGE)}: {name}"
        for p in files
        for name in _imports(p)
        if _hits(name)
    }
    assert not offenders


def test_the_scan_catches_a_forbidden_import(tmp_path):
    bad = tmp_path / "x.py"
    bad.write_text(
        "from backend.app.controllers import form\nimport backend.app.router\n"
    )
    assert any(_hits(n) for n in _imports(bad))


def test_importing_the_package_loads_none_of_them():
    code = (
        "import sys\n"
        "import backend.admin, backend.admin.config, backend.admin.db\n"
        "import backend.admin.security.keys, backend.admin.services.audit\n"
        "import backend.admin.repositories.audit, backend.admin.repositories.tables\n"
        "import backend.admin.__main__\n"
        f"forbidden = {FORBIDDEN!r}\n"
        "bad = [m for m in sys.modules if any(m == b or m.startswith(b + '.') for b in forbidden)]\n"
        "bad += [m for m in sys.modules if m == 'backend.app' or m.startswith('backend.app.')]\n"
        "print('OFFENDERS=' + ','.join(sorted(bad)))\n"
    )
    env = {
        k: v
        for k, v in os.environ.items()
        if k not in {"MASTER_ENCRYPTION_KEYSET", "SETTINGS_MASTER_KEY"}
    }
    done = subprocess.run(
        [sys.executable, "-c", code],
        cwd=BACKEND_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert done.returncode == 0, done.stderr[-2000:]
    assert done.stdout.strip().splitlines()[-1] == "OFFENDERS="
