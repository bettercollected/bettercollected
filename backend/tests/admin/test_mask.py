import json
import random

import pytest

from backend.admin.services.audit import MAX_STRING, REDACTED, canonical_json, mask

DENIED = [
    "secret",
    "client_secret",
    "token",
    "access_token",
    "Password",
    "NEW_PASSWD",
    "api_key",
    "apiKey",
    "code",
    "otp",
    "totp_seed",
    "password_hash",
    "Authorization",
    "Set-Cookie",
    "private_key",
]


def test_denied_keys_are_redacted_at_any_depth_and_case():
    data = {
        "name": "ok",
        "nested": {"Api_Key": "k1", "list": [{"AUTHORIZATION": "Bearer x"}, "plain"]},
        "otp": "123456",
    }
    out = mask(data)
    assert out["name"] == "ok"
    assert out["nested"]["Api_Key"] == REDACTED
    assert out["nested"]["list"][0]["AUTHORIZATION"] == REDACTED
    assert out["nested"]["list"][1] == "plain"
    assert out["otp"] == REDACTED


def test_a_whole_structure_under_a_denied_key_is_replaced():
    assert mask({"secrets": {"a": 1, "b": [1, 2]}}) == {"secrets": REDACTED}


def test_long_strings_are_truncated_and_nul_removed():
    out = mask({"v": "x" * 1000, "n": "a\x00b"})
    assert len(out["v"]) < MAX_STRING + 40 and out["v"].startswith("x" * MAX_STRING)
    assert out["n"] == "ab"


def test_output_survives_a_json_round_trip():
    out = mask({"f": 1.5, "t": (1, 2), "s": {3}, "o": object(), 7: "int key"})
    assert json.loads(canonical_json(out)) == out
    assert out["f"] == "1.5"  # floats become strings so jsonb cannot change them


def test_bounds_on_depth_and_width():
    deep: dict = {}
    cur = deep
    for _ in range(40):
        cur["a"] = {}
        cur = cur["a"]
    assert len(canonical_json(mask(deep))) < 400
    wide = {f"k{i}": i for i in range(500)}
    assert len(mask(wide)) <= 51


def _random_tree(rng: random.Random, planted_values: list[str], depth: int = 0):
    kind = rng.random()
    if depth > 4 or kind < 0.25:
        return rng.choice(["x", 1, True, None, "hello"])
    if kind < 0.6:
        out = {}
        for _ in range(rng.randint(1, 5)):
            if rng.random() < 0.4:
                planted = f"PLANTED-{rng.getrandbits(64):x}"
                planted_values.append(planted)
                key = rng.choice(DENIED)
                key = "".join(c.upper() if rng.random() < 0.5 else c for c in key)
                out[rng.choice(["", "x_", "my-"]) + key] = (
                    planted
                    if rng.random() < 0.5
                    else {"inner": [planted, {"deep": planted}]}
                )
            else:
                out[f"field{rng.randint(0, 99)}"] = _random_tree(
                    rng, planted_values, depth + 1
                )
        return out
    return [
        _random_tree(rng, planted_values, depth + 1) for _ in range(rng.randint(0, 4))
    ]


@pytest.mark.parametrize("seed", range(60))
def test_planted_secrets_never_survive(seed):
    rng = random.Random(seed)
    planted_values: list[str] = []
    tree = _random_tree(rng, planted_values)
    rendered = canonical_json(mask(tree)).decode()
    for planted in planted_values:
        assert planted not in rendered
