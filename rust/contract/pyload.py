"""Import single backend modules without importing the application.

``backend.app.services`` and its siblings import half the application in their
``__init__`` files (and need its settings and optional packages). The modules
the golden vectors call are small and pure, so the packages above them are made
empty (no ``__init__`` runs) and ``backend.config.settings`` is a plain object
the generator sets per case. Nothing here changes the code under test: the
module files are the ones in the repository, executed as they are.
"""

import importlib.abc
import importlib.machinery
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "common"))
BACKEND = ROOT / "backend"

settings = types.SimpleNamespace(
    auth_settings=types.SimpleNamespace(JWT_SECRET="", AES_HEX_KEY=""),
    respondent_identity=types.SimpleNamespace(KEY=""),
)


# small packages whose ``__init__`` the modules under test import from
REAL_PACKAGES = {"backend.app.exceptions"}


class _EmptyPackages(importlib.abc.MetaPathFinder):
    """``backend`` and every package below it, without running ``__init__``."""

    def find_spec(self, fullname, path, target=None):
        if fullname != "backend" and not fullname.startswith("backend."):
            return None
        if fullname in REAL_PACKAGES:
            return None
        if fullname == "backend":
            directory = BACKEND / "backend"
        else:
            directory = BACKEND / "backend" / fullname.split(".", 1)[1].replace(".", "/")
        if (directory / "__init__.py").is_file():
            if fullname == "backend.config":
                return None
            spec = importlib.machinery.ModuleSpec(fullname, None, is_package=True)
            spec.submodule_search_locations = [str(directory)]
            return spec
        return None


def _stub_missing(*names: str) -> None:
    """A package the module imports but never calls here, absent from this
    environment (a stale virtualenv): an empty module stands in."""
    for name in names:
        try:
            __import__(name)
        except ImportError:
            sys.modules[name] = types.ModuleType(name)


def install() -> None:
    _stub_missing("segno")
    if not any(isinstance(f, _EmptyPackages) for f in sys.meta_path):
        sys.meta_path.insert(0, _EmptyPackages())
    config = types.ModuleType("backend.config")
    config.settings = settings
    config.__path__ = [str(BACKEND / "backend" / "config")]
    sys.modules["backend.config"] = config


def extract(path: str, names: tuple, **namespace):
    """Only the named top-level functions and assignments of a module file,
    executed in a namespace of the caller's (for a module whose other imports
    need packages this environment does not have)."""
    import ast

    source = (BACKEND / "backend" / path).read_text()
    tree = ast.parse(source)
    keep = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in names:
            keep.append(node)
        elif isinstance(node, ast.Assign) and any(getattr(t, "id", None) in names for t in node.targets):
            keep.append(node)
    scope = dict(namespace)
    exec(compile(ast.Module(body=keep, type_ignores=[]), path, "exec"), scope)
    return types.SimpleNamespace(**{n: scope[n] for n in names})
