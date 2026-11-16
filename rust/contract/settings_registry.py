"""The settings registry the Rust edge reads the settings store with, written out by
the Python code that defines it.

    uv run --project backend python rust/contract/settings_registry.py            # rewrite the file
    uv run --project backend python rust/contract/settings_registry.py --check    # fail on drift

The Rust reader (rust/bc-config/src/store/) must apply the same rules to a stored
row as the Python loader, and those rules depend on the registry: which keys the
backend may read, their section, secrecy, reload class, tier, type and limits. This
script copies exactly that, for the reader ``backend``, into
rust/bc-config/data/settings-registry.json, which the crate embeds. ``--check``
(a test in test_harness.py runs it) fails when the Python registry moved and the
file did not.

``store_backed`` marks the keys the Python backend actually resolves from the store:
a field of a ``StoreBackedSettings`` class without an alias choice (the loader's
``StoreSource`` skips a field that has more than one name, for example
``TRUSTED_PROXIES``), plus the keys that code resolves directly
(``DIRECT_STORE_READS``). A key that is in the registry but not store backed is not
read from the store by Python, so the Rust side must not read it either.
"""

import importlib
import json
import os
import pkgutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
OUT = REPO / "rust" / "bc-config" / "data" / "settings-registry.json"
sys.path.insert(0, str(REPO / "backend"))
sys.path.insert(0, str(REPO / "common"))

SERVICE = "backend"
# Keys the backend resolves with ``runtime.resolve_key`` itself rather than through a
# settings class (common/services/keyset_source.py).
DIRECT_STORE_READS = ("MASTER_ENCRYPTION_KEYSET",)


def store_backed_keys() -> set:
    """The store keys the backend's settings classes ask the loader for."""
    os.environ.setdefault("SETTINGS_STORE", "off")  # importing the config must not read a store
    from common.settings.loader import pydantic_source
    from common.settings.loader.pydantic_source import StoreBackedSettings

    package = importlib.import_module("backend.config")
    for module in pkgutil.iter_modules(package.__path__):
        importlib.import_module(f"backend.config.{module.name}")

    keys = set(DIRECT_STORE_READS)
    seen, todo = set(), [StoreBackedSettings]
    while todo:
        cls = todo.pop()
        for sub in cls.__subclasses__():
            if sub in seen:
                continue
            seen.add(sub)
            todo.append(sub)
            if not sub.__module__.startswith("backend."):
                continue
            for name, field in sub.model_fields.items():
                names = pydantic_source._env_name(sub, name, field)
                if names is not None:
                    keys.add(names[1])
    return keys


def build() -> dict:
    from common.settings.inventory import RETIRED, full_registry

    registry = full_registry()
    backed = store_backed_keys()
    specs = []
    others = []
    for spec in sorted(registry, key=lambda s: s.key):
        if SERVICE not in spec.readers:
            others.append(spec.key)
            continue
        specs.append(
            {
                "key": spec.key,
                "section": spec.section,
                "readers": sorted(spec.readers),
                "retired_readers": sorted(spec.retired_readers),
                "type": spec.type.value,
                "is_secret": spec.is_secret,
                "reload": spec.reload_class.value,
                "tier": spec.tier.value,
                "choices": list(spec.choices),
                "min": spec.min_value,
                "max": spec.max_value,
                "max_length": spec.max_length,
                "format": spec.format,
                "store_backed": spec.key in backed,
            }
        )
    return {
        "service": SERVICE,
        "specs": specs,
        "other_known": others,
        "retired": sorted(RETIRED),
    }


def render(data: dict) -> str:
    return json.dumps(data, indent=1, sort_keys=True) + "\n"


def main() -> int:
    check = "--check" in sys.argv[1:]
    text = render(build())
    if check:
        if not OUT.exists() or OUT.read_text() != text:
            print(
                "rust/bc-config/data/settings-registry.json is out of date: run "
                "`uv run --project backend python rust/contract/settings_registry.py`"
            )
            return 1
        print("settings registry file is current")
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text)
    print(f"wrote {OUT.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
