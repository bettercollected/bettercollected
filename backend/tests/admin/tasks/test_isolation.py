"""Who may import what: the admin web process sees task metadata only; the
runner never loads the public application or the shared crypto service."""

from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path

import pytest

import backend.admin

PACKAGE = Path(backend.admin.__file__).parent
TASKS = PACKAGE / "tasks"
BACKEND_ROOT = PACKAGE.parents[1]
RUNNER_SIDE = ("backend.admin.tasks.impl", "backend.admin.tasks.runner", "backend.admin.runner")
# the runner may use the keyset module (common.services.keyset) but not the crypto
# singleton or anything else of the shared services
PUBLIC = ("backend.app", "common.services.crypto_service")


def _imports(path: Path):
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            yield base
            for alias in node.names:
                yield f"{base}.{alias.name}"


def _under(name: str, prefixes) -> bool:
    return any(name == p or name.startswith(p + ".") for p in prefixes)


def _is_runner_side(path: Path) -> bool:
    rel = path.relative_to(PACKAGE).as_posix()
    return (
        rel.startswith(("tasks/impl/", "tasks/runner/"))
        or rel in ("runner.py", "tasks/impl/__init__.py")
    )


def test_only_the_runner_side_imports_implementations_or_the_runner():
    files = [p for p in PACKAGE.rglob("*.py") if not _is_runner_side(p)]
    assert len(files) > 20
    offenders = [
        f"{p.relative_to(PACKAGE)}: {n}"
        for p in files
        for n in _imports(p)
        if _under(n, RUNNER_SIDE)
    ]
    assert offenders == []


def test_the_scan_catches_an_implementation_import(tmp_path):
    bad = tmp_path / "x.py"
    bad.write_text("from backend.admin.tasks.impl import selftest\n")
    assert any(_under(n, RUNNER_SIDE) for n in _imports(bad))


def test_the_runner_side_imports_no_public_application_module():
    files = [p for p in PACKAGE.rglob("*.py") if _is_runner_side(p)] + [
        TASKS / n for n in ("spec.py", "registry.py", "signing.py", "sanitiser.py", "tables.py")
    ]
    offenders = [
        f"{p.relative_to(PACKAGE)}: {n}"
        for p in files
        for n in _imports(p)
        if _under(n, PUBLIC)
    ]
    assert offenders == []


def test_the_runner_side_uses_only_the_keyset_of_the_shared_services():
    files = [p for p in PACKAGE.rglob("*.py") if _is_runner_side(p)]
    used = {
        n
        for p in files
        for n in _imports(p)
        if n.startswith("common.services") and n != "common.services"
    }
    assert {n for n in used if not n.startswith("common.services.keyset")} == set()


def test_spec_is_pure_metadata():
    stdlib = set(sys.stdlib_module_names)
    for name in _imports(TASKS / "spec.py"):
        top = name.split(".")[0]
        assert top in stdlib or top == "pydantic" or name.startswith("__future__"), name


def _run(code: str, **extra_env) -> list[str]:
    env = {
        k: v for k, v in os.environ.items() if k not in {"MASTER_ENCRYPTION_KEYSET", "SETTINGS_MASTER_KEY"}
    }
    env.update(extra_env)
    done = subprocess.run(
        [sys.executable, "-c", code],
        cwd=BACKEND_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert done.returncode == 0, done.stderr[-1500:]
    line = [l for l in done.stdout.splitlines() if l.startswith("LOADED=")][-1]
    return [m for m in line[len("LOADED="):].split(",") if m]


@pytest.mark.parametrize("selftest", ["0", "1"])
def test_the_web_side_loads_no_implementation_even_with_the_selftest_flag(selftest):
    loaded = _run(
        "import sys\n"
        "import backend.admin.tasks.spec, backend.admin.tasks.registry\n"
        "import backend.admin.tasks.signing, backend.admin.tasks.sanitiser\n"
        "import backend.admin.tasks.catalog as c\n"
        "c.all_meta()\n"
        "bad = [m for m in sys.modules if m.startswith(('backend.admin.tasks.impl',"
        " 'backend.admin.tasks.runner', 'backend.admin.runner', 'backend.app',"
        " 'common.services.crypto'))]\n"
        "print('LOADED=' + ','.join(sorted(bad)))\n",
        ADMIN_TASKS_SELFTEST=selftest,
    )
    assert loaded == []


def test_the_admin_asgi_app_loads_no_implementation():
    loaded = _run(
        "import sys\n"
        "import backend.admin.asgi\n"
        "bad = [m for m in sys.modules if m.startswith(('backend.admin.tasks.impl',"
        " 'backend.admin.tasks.runner', 'backend.admin.runner'))]\n"
        "print('LOADED=' + ','.join(sorted(bad)))\n",
        ADMIN_TASKS_SELFTEST="1",
    )
    assert loaded == []


def test_the_runner_loads_no_public_application_or_crypto_service():
    loaded = _run(
        "import sys\n"
        "import backend.admin.runner\n"
        "import backend.admin.tasks.runner.main as m\n"
        "m.impl.build_registry({'ADMIN_TASKS_SELFTEST': '1'})\n"
        "bad = [m for m in sys.modules if m == 'backend.app' or m.startswith(('backend.app.',"
        " 'common.services.crypto_service', 'backend.app.router', 'backend.app.container'))]\n"
        "print('LOADED=' + ','.join(sorted(bad)))\n",
        ADMIN_TASKS_SELFTEST="1",
    )
    assert loaded == []
