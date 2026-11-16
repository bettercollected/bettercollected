"""Golden vectors for ``bc-crypto``: values the Python backend's own code writes.

Run from the repository root (the vectors use throw-away keys generated here,
never real ones; no application settings or database are needed)::

    uv run --no-sync --project backend python rust/contract/golden_crypto.py fernet rust/bc-crypto/tests/golden/fernet_vector.json
    uv run --no-sync --project backend python rust/contract/golden_crypto.py derived rust/bc-crypto/tests/golden/derived_vector.json

and the other direction (Rust writes, Python opens), after
``RUST_SEALED_OUT=/path cargo test -p bc-crypto``::

    uv run --no-sync --project backend python rust/contract/golden_crypto.py check-fernet <vector> <RUST_SEALED_OUT>
    uv run --no-sync --project backend python rust/contract/golden_crypto.py check-derived <vector> <RUST_SEALED_OUT>
"""

import base64
import json
import sys
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken, MultiFernet

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pyload  # noqa: E402

pyload.install()

from common.configs.crypto import Crypto  # noqa: E402

T0 = 1_700_000_000


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


# ---------------------------------------------------------------- Fernet ----


def sealed_at(key: str, plaintext: str, now: int, iv: bytes) -> str:
    """What ``Crypto.encrypt`` produces for the first key of a ring, at a given
    time and with a given IV (``Fernet._encrypt_from_parts``, the one
    ``Fernet.encrypt`` itself calls)."""
    return Fernet(key)._encrypt_from_parts(plaintext.encode(), now, iv).decode()


def python_opens(ring: str, token, ttl, now):
    """The plaintext Python's ring opens ``token`` to at ``now``, or None."""
    crypto = Crypto(ring)
    try:
        if ttl is None:  # no time limit: the clock plays no part
            return crypto.decrypt(token)
        return crypto._ring.decrypt_at_time(token, ttl, now).decode()
    except (InvalidToken, TypeError, ValueError):
        return None


def mutate(token: str):
    """Damaged copies of a token, each named by what was done to it."""
    raw = bytearray(base64.urlsafe_b64decode(token))

    def enc(data) -> str:
        return base64.urlsafe_b64encode(bytes(data)).decode()

    out = {}
    for name, index in (
        ("version", 0),
        ("timestamp", 3),
        ("iv", 12),
        ("ciphertext", 27),
        ("tag", len(raw) - 3),
    ):
        copy = bytearray(raw)
        copy[index] ^= 0x01
        out[f"flip {name}"] = enc(copy)
    out["truncated tag"] = enc(raw[:-1])
    out["truncated half"] = enc(raw[: len(raw) // 2])
    out["truncated to header"] = enc(raw[:25])
    out["empty"] = ""
    out["extra byte"] = enc(bytes(raw) + b"\x00")
    out["not base64"] = "!!!not a token!!!"
    out["token with a newline"] = token + "\n"
    out["token with a space inside"] = token[:10] + " " + token[10:]
    out["unpadded"] = token.rstrip("=")
    out["junk after the padding"] = token + "AAAA"
    out["non-ascii"] = token[:8] + "é" + token[8:]
    # a validly signed token of the wrong shape cannot be made without the key,
    # so these are all refusals
    return out


def fernet_vector() -> dict:
    k1, k2, k3 = (Fernet.generate_key().decode() for _ in range(3))
    iv = bytes(range(16))
    plaintexts = {
        "text": "héllo wörld",
        "empty": "",
        "block": "0123456789abcdef",
        "long": "secret answer " * 30,
        "json": json.dumps({"v": 1, "workspace_id": "w", "secret": "s"}),
    }
    cases = []

    def add(name, ring, token, ttl=None, now=T0):
        cases.append(
            {
                "name": name,
                "ring": ring,
                "token": token,
                "ttl": ttl,
                "now": now,
                "expect": python_opens(ring, token, ttl, now),
            }
        )

    for label, text in plaintexts.items():
        t1 = sealed_at(k1, text, T0, iv)
        t2 = sealed_at(k2, text, T0, iv)
        add(f"{label}: sealed with the current key, ring of one", k1, t1)
        add(f"{label}: sealed with the current key, ring of two", f"{k1},{k2}", t1)
        # rotation: sealed with the previous key, opened with the ring
        add(f"{label}: sealed with the previous key, opened by the ring", f"{k1},{k2}", t2)
        add(f"{label}: sealed with the previous key, ring has only the new one", k1, t2)
        add(f"{label}: wrong key", k3, t1)
        add(f"{label}: wrong ring", f"{k3},{k2}", t1)

    base = sealed_at(k1, plaintexts["text"], T0, iv)
    for ttl, now, name in (
        (60, T0 + 10, "inside the limit"),
        (60, T0 + 60, "exactly at the limit"),
        (60, T0 + 61, "one second past the limit"),
        (60, T0 - 30, "stamped 30 s ahead"),
        (60, T0 - 60, "stamped exactly 60 s ahead"),
        (60, T0 - 61, "stamped 61 s ahead"),
        (0, T0, "a zero limit, same second"),
        (0, T0 + 1, "a zero limit, next second"),
        (3600, T0 + 3600, "the OAuth state limit, at the edge"),
        (3600, T0 + 3601, "the OAuth state limit, past the edge"),
        (None, T0 + 10**8, "no limit, long after"),
        (None, T0 - 10**6, "no limit, stamped far ahead"),
    ):
        add(f"ttl: {name}", f"{k1},{k2}", base, ttl, now)
    # a previous-key token past its limit is refused by the ring too
    add("ttl: previous key, past the limit", f"{k1},{k2}", sealed_at(k2, "x", T0, iv), 60, T0 + 61)

    for name, token in mutate(base).items():
        add(f"damaged: {name}", f"{k1},{k2}", token)
        add(f"damaged (with ttl): {name}", f"{k1},{k2}", token, 3600, T0 + 5)
    for name, token in mutate(sealed_at(k1, "", T0, iv)).items():
        add(f"damaged empty value: {name}", k1, token)

    keys_for_shape = {
        "quoted ring": f'"{k1}","{k2}"',
    }
    # key text as an env file writes it: surrounding quotes and spaces
    quoted = f'"{k1},{k2}"'
    add("ring text in quotes", quoted, sealed_at(k2, "q", T0, iv))
    add("ring text with spaces around the comma", f"{k1} , {k2}", sealed_at(k2, "q", T0, iv))
    del keys_for_shape

    # a fresh Crypto.encrypt (real time, random IV) opens with ttl None
    crypto = Crypto(f"{k1},{k2}")
    fresh = [crypto.encrypt(t) for t in plaintexts.values()]
    for text, token in zip(plaintexts.values(), fresh):
        cases.append(
            {
                "name": "Crypto.encrypt output",
                "ring": f"{k1},{k2}",
                "token": token,
                "ttl": None,
                "now": None,
                "expect": text,
            }
        )

    # sealed envelopes of the backend (registration secret, webhook address, TOTP secret)
    from backend.app.services.registration import secrets as registration_secrets
    from backend.app.services.webhooks import sealing as webhook_sealing
    from backend.app.services.mfa import sealing as mfa_sealing

    ws, other = "6a0000000000000000000001", "6a0000000000000000000009"
    svc, hook, user, factor = (
        "6a00000000000000000000a1",
        "6a00000000000000000000b1",
        "6a00000000000000000000c1",
        "6a00000000000000000000d1",
    )
    envelopes = {
        "registration": {
            "args": [ws, svc],
            "wrong_args": [other, svc],
            "plaintext": "s3cr3t-ünï",
            "sealed": registration_secrets.seal(crypto, ws, svc, "s3cr3t-ünï"),
        },
        "webhook_url": {
            "args": [ws, hook],
            "wrong_args": [ws, other],
            "plaintext": "https://hooks.voorbeeld.example/in?key=abc",
            "sealed": webhook_sealing.seal_url(crypto, ws, hook, "https://hooks.voorbeeld.example/in?key=abc"),
        },
        "totp_secret": {
            "args": [user, factor],
            "wrong_args": [user, other],
            "plaintext": "JBSWY3DPEHPK3PXP",
            "sealed": mfa_sealing.seal_secret(crypto, user, factor, "JBSWY3DPEHPK3PXP"),
        },
    }
    # an envelope of one purpose is never another's
    envelopes["registration"]["as_webhook"] = envelopes["webhook_url"]["sealed"]
    envelopes["webhook_url"]["as_totp"] = envelopes["totp_secret"]["sealed"]
    envelopes["totp_secret"]["as_webhook"] = envelopes["webhook_url"]["sealed"]

    return {
        "keys": {"k1": k1, "k2": k2, "k3": k3},
        "t0": T0,
        "iv_hex": iv.hex(),
        "plaintexts": plaintexts,
        "cases": cases,
        "envelopes": {"ring": f"{k1},{k2}", **envelopes},
    }


def check_fernet(vector_path: str, rust_path: str) -> None:
    """Python opens what Rust sealed, and Python's own seal of the same value
    at the same time and IV is byte for byte the same token."""
    vector = json.loads(Path(vector_path).read_text())
    rust = json.loads(Path(rust_path + ".fernet.json").read_text())
    count = 0
    for item in rust["fernet"]:
        crypto = Crypto(item["ring"])
        opened = python_opens(item["ring"], item["token"], item.get("ttl"), item["now"])
        assert opened == item["plaintext"], item["name"]
        if item.get("iv_hex"):
            first = item["ring"].split(",")[0]
            same = sealed_at(first, item["plaintext"], item["now"], bytes.fromhex(item["iv_hex"]))
            assert same == item["token"], f"{item['name']}: Rust and Python seal differently"
        count += 1
    from backend.app.services.registration import secrets as registration_secrets
    from backend.app.services.webhooks import sealing as webhook_sealing
    from backend.app.services.mfa import sealing as mfa_sealing

    ring = Crypto(vector["envelopes"]["ring"])
    env = rust["envelopes"]
    assert registration_secrets.unseal(ring, *env["registration"]["args"], env["registration"]["sealed"]) == env["registration"]["plaintext"]
    assert webhook_sealing.unseal_url(ring, *env["webhook_url"]["args"], env["webhook_url"]["sealed"]) == env["webhook_url"]["plaintext"]
    assert mfa_sealing.unseal_secret(ring, *env["totp_secret"]["args"], env["totp_secret"]["sealed"]) == env["totp_secret"]["plaintext"]
    print(f"python opened {count} rust-sealed tokens and 3 envelopes: ok")


# ------------------------------------------------------- the other values ----




def main() -> None:
    command, *args = sys.argv[1:]
    if command == "fernet":
        Path(args[0]).parent.mkdir(parents=True, exist_ok=True)
        # throw-away keys generated for this vector (the Rust tests need them to
        # open the tokens); test data, replaced on every regeneration
        Path(args[0]).write_text(json.dumps(fernet_vector(), indent=1, ensure_ascii=True))
        print("wrote", args[0])
    elif command == "check-fernet":
        check_fernet(*args)
    elif command in ("derived", "check-derived"):
        from derived_vectors import run  # noqa: WPS433  (added with the derived section)

        run(command, args)
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
