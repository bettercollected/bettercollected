import re

import pytest

from common.security import recovery


def test_codes_have_the_documented_shape():
    codes = {recovery.generate_code() for _ in range(recovery.CODE_COUNT)}
    assert len(codes) == recovery.CODE_COUNT == 10
    for code in codes:
        assert re.fullmatch(r"[A-Z2-7]{4}(-[A-Z2-7]{4}){3}", code)
        assert recovery.is_well_formed(code)


def test_normalisation_makes_formatting_irrelevant():
    code = recovery.generate_code()
    variants = [
        code.lower(),
        code.replace("-", ""),
        code.replace("-", " "),
        f"  {code} ",
        f"\t{code}\n",
    ]
    assert {recovery.normalise(v) for v in variants + [code]} == {code.replace("-", "")}


@pytest.mark.parametrize(
    "garbage",
    ["", "short", "!" * 16, "A" * 17, "A" * 15, "0189-0189-0189-0189", None, 12345],
)
def test_garbage_is_not_well_formed_and_never_raises(garbage):
    assert recovery.is_well_formed(garbage) is False


def test_well_formed_accepts_the_spaced_and_lowercase_forms():
    code = recovery.generate_code()
    assert recovery.is_well_formed(code.lower().replace("-", " "))
