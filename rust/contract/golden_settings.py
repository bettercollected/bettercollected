"""Write the golden vector of the Rust settings-store reader: rows, a manifest and sealed
secrets that the Python settings code itself signed and sealed under throw-away master keys.

    uv run --project backend python rust/contract/golden_settings.py rust/bc-config/tests/golden/settings_store.json

The report fingerprints (what a service tells the store about its keys) are added to the
same file without touching the rest (sealing uses fresh nonces, so a full run rewrites every
blob)::

    uv run --project backend python rust/contract/golden_settings.py fingerprints rust/bc-config/tests/golden/settings_store.json

The keys are generated for the tests only (fixed bytes, so the file is stable). The Rust
tests (rust/bc-config/tests/settings_store_golden.rs) rebuild every derived key, signature and
canonical byte string and open every sealed value, and compare them with this file.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "common"))

import base64  # noqa: E402

from common.settings.canonical import SettingRow, canonical_manifest, canonical_row  # noqa: E402
from common.settings.crypto.keys import derive_from_master  # noqa: E402
from common.settings.keys import SectionKeys  # noqa: E402

MASTER = base64.b64encode(bytes(range(100, 148))).decode()
PREVIOUS = base64.urlsafe_b64encode(bytes((7 * i + 3) % 256 for i in range(40))).decode().rstrip("=")
SECTIONS = ["features", "sso", "rate_limits", "auth_keys"]
STAMP = datetime(2026, 11, 16, 9, 8, 7, 654321, tzinfo=timezone.utc)

PLAIN = [
    # key, section, readers, reload, value
    ("FIELD_RULES_ENABLED", "features", ("backend",), "R", True),
    ("SSO_ENABLED", "sso", ("webapp", "backend", "auth"), "R", False),
    ("API_FLOW_EVENTS_PER_WINDOW", "rate_limits", ("backend",), "H", 600),
    ("SSO_HTTP_TIMEOUT_SECONDS", "sso", ("backend", "auth"), "R", 15.0),
    ("TINY_FLOAT", "features", ("backend",), "R", 1e-05),
    ("HUGE_FLOAT", "features", ("backend",), "R", 1.5e16),
    ("TEXT", "features", ("backend",), "R", "café “quoted” \U0001f600 \u007f tab\there"),
    ("NESTED", "features", ("backend",), "R", {"b": [1, 2.5, None], "a": {"z": 1, "y": "ü"}}),
]
SECRETS = [
    ("AUTH_JWT_SECRET", "auth_keys", ("backend", "auth", "google"), "R",
     "golden-jwt-secret-0123456789abcdef0123456789abcdef"),
    ("MASTER_ENCRYPTION_KEYSET", "auth_keys", ("backend", "google"), "R",
     "Z29sZGVuLWtleXNldC12YWx1ZS1ub3QtYS1yZWFsLW9uZQ=="),
]


def row_json(row: SettingRow) -> dict:
    return {
        "key": row.key, "section": row.section, "readers": list(row.readers),
        "is_secret": row.is_secret, "reload_class": row.reload_class, "version": row.version,
        "updated_at": STAMP.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "value": row.value, "blob": row.blob, "sig": row.sig,
    }


def main(out: str) -> None:
    keys = SectionKeys(MASTER, sections=SECTIONS, master_previous=PREVIOUS)
    only_previous = SectionKeys(PREVIOUS, sections=SECTIONS)
    rows = []
    for version, (key, section, readers, reload, value) in enumerate(PLAIN, start=2):
        rows.append(keys.sign_row(SettingRow(key, section, readers, False, reload, version, STAMP, value=value)))
    sealed = []
    for version, (key, section, readers, reload, plain) in enumerate(SECRETS, start=5):
        blob = keys.seal(section, key, version, plain)
        rows.append(keys.sign_row(SettingRow(key, section, readers, True, reload, version, STAMP, blob=blob)))
        # the same value sealed under the PREVIOUS master key only (a rotation in progress)
        old_blob = only_previous.seal(section, key, version, plain)
        sealed.append({"key": key, "section": section, "version": version, "plaintext": plain,
                       "blob": blob, "blob_previous_key": old_blob})
    manifest = keys.sign_manifest(7, rows)
    out_rows = []
    for row in rows:
        out_rows.append({**row_json(row), "canonical_hex": canonical_row(row).hex()})
    data = {
        "master": MASTER,
        "master_previous": PREVIOUS,
        "sections": SECTIONS,
        "derived": {
            "manifest_sign": derive_from_master(__import__("base64").b64decode(MASTER), "settings", "sign").hex(),
            "row_sign_features": derive_from_master(base64.b64decode(MASTER), "settings", "sign", 1, "features").hex(),
            "wrap_auth_keys": derive_from_master(base64.b64decode(MASTER), "settings", "wrap", 1, "auth_keys").hex(),
        },
        "rows": out_rows,
        "sealed": sealed,
        "manifest": {
            **keys.sign_manifest(7, rows).to_json(),
            "canonical_hex": canonical_manifest(7, {r.key: (r.version, r.sig, tuple(r.readers)) for r in rows}).hex(),
        },
    }
    assert manifest.sig == data["manifest"]["sig"]
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(json.dumps(data, indent=1, sort_keys=True) + "\n")
    print(f"wrote {out}: {len(out_rows)} rows, {len(sealed)} sealed secrets")


def fingerprints(out: str) -> None:
    """``SectionKeys.fingerprint`` (the settings master key's id) and ``keyset_fingerprint``
    (the key ids of a keyset), as Python computes them: the values a service reports as
    ``keyset_fp``. Written into the existing file under "fingerprints"."""
    from common.settings.loader.runtime import keyset_fingerprint

    path = Path(out)
    data = json.loads(path.read_text())
    data["fingerprints"] = {
        "master": SectionKeys(MASTER, sections=SECTIONS).fingerprint,
        "master_with_previous": SectionKeys(MASTER, sections=SECTIONS, master_previous=PREVIOUS).fingerprint,
        "previous_only": SectionKeys(PREVIOUS, sections=SECTIONS).fingerprint,
        "keyset_ids": [
            {"ids": ids, "fp": keyset_fingerprint(ids)}
            for ids in ([1], [7], [300, 7], [7, 300], [4294967295, 1, 10, 2], [10, 9, 100], [1, 2, 3])
        ],
        "report_mark": __import__("common.settings.key_ring", fromlist=["REPORT_MARK"]).REPORT_MARK,
    }
    path.write_text(json.dumps(data, indent=1, sort_keys=True) + "\n")
    print(f"wrote fingerprints into {out}")


if __name__ == "__main__":
    if sys.argv[1] == "fingerprints":
        fingerprints(sys.argv[2])
    else:
        main(sys.argv[1])
