"""Write a golden vector for the Rust crypto test: a throw-away Tink keyset and
values the Python backend's own CryptoService sealed under it.

    uv run --project backend python rust/contract/golden_tink.py rust/bc-api/tests/golden/tink_vector.json

The keyset is generated here and used by tests only. The vector also holds a
Rust-written value when ``--check`` is given a file with one (see tests).
"""

import base64
import io
import json
import sys
from pathlib import Path

import tink
from tink import JsonKeysetWriter, aead, cleartext_keyset_handle

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
from common.services.keyset import CryptoService  # noqa: E402

aead.register()


def keyset(template) -> str:
    handle = tink.new_keyset_handle(template)
    buffer = io.StringIO()
    cleartext_keyset_handle.write(JsonKeysetWriter(buffer), handle)
    return base64.b64encode(buffer.getvalue().encode()).decode()


def make(path: str) -> None:
    out = {"cases": []}
    for name, template in (
        ("aes256", aead.aead_key_templates.AES256_GCM),
        ("aes128", aead.aead_key_templates.AES128_GCM),
    ):
        ks = keyset(template)
        svc = CryptoService(ks)
        cases = []
        for ws, form, text, ctx in (
            ("6a0000000000000000000001", "6a0000000000000000000002", '{"q1":{"type":"text","text":"héllo"}}', b""),
            ("6a0000000000000000000001", "6a0000000000000000000002", "x", b'["resp","fld","file"]'),
            ("w", "f", "", b""),
        ):
            sealed = svc.encrypt(ws, form, text, ctx)
            cases.append(
                {
                    "workspace_id": ws,
                    "form_id": form,
                    "context_b64": base64.b64encode(ctx).decode(),
                    "plaintext": text,
                    "stored_b64": base64.b64encode(sealed).decode(),
                }
            )
        out["cases"].append({"name": name, "keyset": ks, "values": cases})
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(out, indent=1))
    print("wrote", path)


def check(path: str, rust_file: str) -> None:
    """Python opens what Rust sealed (rust_file: JSON written by the Rust test)."""
    vector = json.loads(Path(path).read_text())
    rust = json.loads(Path(rust_file).read_text())
    case = {c["name"]: c for c in vector["cases"]}[rust["name"]]
    svc = CryptoService(case["keyset"])
    opened = svc.decrypt(
        rust["workspace_id"],
        rust["form_id"],
        base64.b64decode(rust["stored_b64"]),
        base64.b64decode(rust["context_b64"]),
    )
    assert opened.decode() == rust["plaintext"], "Python did not open what Rust sealed"
    print("python opened the rust-written value: ok")


if __name__ == "__main__":
    if sys.argv[1] == "--check":
        check(sys.argv[2], sys.argv[3])
    else:
        make(sys.argv[1])
