"""Finds every environment variable name the services read, by reading source
(no imports, so no service has to be installed): the fields of the pydantic
settings classes (with their prefixes and aliases), literal names passed to
``os.environ``/``os.getenv``/``env.get`` and the small env helpers, the key
constants of the modules that parse their own environment, the webapp's
``process.env`` reads, and the names listed in env example and compose files.
"""

import ast
import re
import warnings
from pathlib import Path
from typing import Dict, Iterable, Iterator, Set

ROOT = Path(__file__).resolve().parents[3]

NAME = re.compile(r"^[A-Z][A-Z0-9_]{2,}$")
SETTINGS_DIRS = (
    "backend/backend/config",
    "auth/auth/config",
    "integrations/google/googleform/config",
    "temporal/worker/settings",
    "temporal/actions-executor/settings",
)
SOURCE_DIRS = (
    "backend/backend",
    "auth/auth",
    "integrations/google/googleform",
    "temporal/worker",
    "temporal/actions-executor",
    "common/common",
)
SKIP_PARTS = {"tests", "migrations", "versions", ".venv", "node_modules", "scripts"}
BARE_NAMES = {"PORT", "DEBUG"}
ENV_RECEIVERS = {"environ", "env", "source", "os.environ"}
ENV_HELPERS = {"_int", "_bool", "_float", "flag", "_networks", "_env", "_str"}
ENV_FILES = (
    ".env.deployment.example",
    "auth/.env.example",
    "backend/.env.example",
    "integrations/google/.env.example",
    "temporal/actions-executor/.env.example",
    "temporal/worker/.env.example",
    "webapp/.env.example",
)
COMPOSE_FILES = (
    "docker-compose.deployment.yml",
    "docker-compose.local.yml",
    "docker-compose.sso-deployment.yml",
    "docker-compose.sso.yml",
)


def _py_files(directories: Iterable[str]) -> Iterator[Path]:
    for directory in directories:
        for path in sorted((ROOT / directory).rglob("*.py")):
            if not SKIP_PARTS.intersection(path.relative_to(ROOT).parts):
                yield path


def _dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{_dotted(node.value)}.{node.attr}"
    return ""


def _literal(node: ast.AST) -> str:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return ""


def _prefix(cls: ast.ClassDef) -> str:
    """``env_prefix`` from ``model_config = SettingsConfigDict(...)`` or an
    inner ``class Config``."""
    for node in cls.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "model_config" for t in node.targets
        ):
            for kw in getattr(node.value, "keywords", []):
                if kw.arg == "env_prefix":
                    return _literal(kw.value)
        if isinstance(node, ast.ClassDef) and node.name == "Config":
            for item in node.body:
                if isinstance(item, ast.Assign) and any(
                    isinstance(t, ast.Name) and t.id == "env_prefix" for t in item.targets
                ):
                    return _literal(item.value)
    return ""


def settings_fields() -> Dict[str, str]:
    """env name -> ``file:Class.field`` for every pydantic settings field."""
    trees = {p: ast.parse(p.read_text()) for d in SETTINGS_DIRS for p in _py_files([d])}
    classes = {
        node.name
        for tree in trees.values()
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef)
        and any(_dotted(b).endswith(("BaseSettings", "StoreBackedSettings")) for b in node.bases)
    }
    found: Dict[str, str] = {}
    for path, tree in trees.items():
        for cls in (n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)):
            if cls.name not in classes:
                continue
            prefix = _prefix(cls)
            for node in cls.body:
                if not isinstance(node, ast.AnnAssign) or not isinstance(node.target, ast.Name):
                    continue
                field = node.target.id
                if field == "model_config" or field.startswith("_"):
                    continue
                value = node.value
                if isinstance(value, ast.Call) and _dotted(value.func) in classes:
                    continue  # a nested settings object
                names = [prefix + field]
                if isinstance(value, ast.Call) and _dotted(value.func).endswith("Field"):
                    for kw in value.keywords:
                        if kw.arg == "validation_alias" and isinstance(kw.value, ast.Call):
                            names = [_literal(a) for a in kw.value.args if _literal(a)]
                for name in names:
                    found[name.upper()] = f"{path.relative_to(ROOT)}:{cls.name}.{field}"
    return found


def env_reads() -> Dict[str, str]:
    """env name -> file for literal reads outside the settings classes."""
    found: Dict[str, str] = {}
    for path in _py_files(SOURCE_DIRS):
        text = path.read_text()
        rel = str(path.relative_to(ROOT))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")  # invalid escapes in old regex strings
            tree = ast.parse(text)
        reads_env = "environ" in text or "env.get" in text or "getenv" in text
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Call):
                func = node.func
                dotted = _dotted(func)
                receiver = _dotted(func.value) if isinstance(func, ast.Attribute) else ""
                if dotted == "os.getenv" or (
                    isinstance(func, ast.Attribute)
                    and func.attr in ("get", "pop")
                    and receiver in ENV_RECEIVERS
                ):
                    names = [_literal(node.args[0])] if node.args else []
                elif dotted.split(".")[-1] in ENV_HELPERS:
                    names = [_literal(a) for a in node.args[:2]]
            elif isinstance(node, ast.Subscript) and _dotted(node.value) in ENV_RECEIVERS:
                names = [_literal(node.slice)]
            elif isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
                for target in node.targets:
                    if isinstance(target, ast.Name) and (
                        target.id.endswith("_ENV") or (reads_env and target.id.endswith("KEY"))
                    ):
                        names = [_literal(node.value)]
            for name in names:
                if NAME.match(name) and ("_" in name or name in BARE_NAMES):
                    found.setdefault(name, rel)
    return found


def webapp_reads() -> Dict[str, str]:
    found: Dict[str, str] = {}
    pattern = re.compile(r"process\.env\.([A-Z][A-Z0-9_]+)|env\.([A-Z][A-Z0-9_]+) \?\?")
    files = [ROOT / "webapp/next.config.js", ROOT / "webapp/entrypoint.sh"]
    files += sorted((ROOT / "webapp/src").rglob("*.ts*"))
    for path in files:
        if not path.is_file() or ".test." in path.name:
            continue
        text = path.read_text()
        for match in pattern.finditer(text):
            found.setdefault(match.group(1) or match.group(2), str(path.relative_to(ROOT)))
        if path.suffix == ".sh":
            for name in re.findall(r"\$\{?(ELASTIC_APM_[A-Z_]+)", text):
                found.setdefault(name, str(path.relative_to(ROOT)))
    return found


def listed_names() -> Dict[str, str]:
    """Names in env example files and compose ``${...}`` interpolations."""
    found: Dict[str, str] = {}
    for name in ENV_FILES:
        path = ROOT / name
        if path.is_file():
            for match in re.finditer(r"^#?\s*([A-Z][A-Z0-9_]+)=", path.read_text(), re.M):
                found.setdefault(match.group(1), name)
    for name in COMPOSE_FILES:
        path = ROOT / name
        if path.is_file():
            text = path.read_text()
            for match in re.finditer(r"\$\{([A-Z][A-Z0-9_]+)", text):
                found.setdefault(match.group(1), name)
    return found


def all_names() -> Dict[str, str]:
    found: Dict[str, str] = {}
    for source in (settings_fields(), env_reads(), webapp_reads(), listed_names()):
        for name, where in source.items():
            found.setdefault(name, where)
    return found


def code_names() -> Set[str]:
    """Names some service reads in code (not merely listed in a file)."""
    return set(settings_fields()) | set(env_reads()) | set(webapp_reads())
