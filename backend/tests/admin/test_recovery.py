import re

import pytest

from backend.admin.security import recovery

PEPPER = b"p" * 32


def test_codes_have_the_documented_shape():
    issued = recovery.issue(PEPPER)
    codes = issued.reveal()
    assert len(codes) == 10 and len(set(codes)) == 10
    for code in codes:
        assert re.fullmatch(r"[A-Z2-7]{4}(-[A-Z2-7]{4}){3}", code)
        assert recovery.is_well_formed(code)
    assert len(issued.hashes) == 10 and len(set(issued.hashes)) == 10


def test_plaintext_is_revealed_exactly_once_and_never_in_repr():
    issued = recovery.issue(PEPPER)
    assert "count=10" in repr(issued)
    codes = issued.reveal()
    with pytest.raises(RuntimeError):
        issued.reveal()
    assert all(code not in repr(issued) for code in codes)
    assert all(code not in h for code in codes for h in issued.hashes)


def test_normalisation_makes_formatting_irrelevant():
    code = recovery.generate_code()
    variants = [
        code.lower(),
        code.replace("-", ""),
        code.replace("-", " "),
        f"  {code} ",
    ]
    hashes = {recovery.hash_code(PEPPER, v) for v in variants + [code]}
    assert len(hashes) == 1
    assert len(next(iter(hashes))) == 64


def test_hash_depends_on_pepper():
    code = recovery.generate_code()
    assert recovery.hash_code(b"a" * 32, code) != recovery.hash_code(b"b" * 32, code)


def test_verify_returns_the_matching_index_or_none():
    issued = recovery.issue(PEPPER)
    codes = issued.reveal()
    for index in (0, 4, 9):
        assert recovery.verify(PEPPER, codes[index], issued.hashes) == index
        spaced = codes[index].lower().replace("-", " ")
        assert recovery.verify(PEPPER, spaced, issued.hashes) == index
    assert recovery.verify(PEPPER, recovery.generate_code(), issued.hashes) is None
    assert recovery.verify(b"x" * 32, codes[0], issued.hashes) is None


def test_verify_ignores_burned_slots_and_garbage():
    issued = recovery.issue(PEPPER)
    codes = issued.reveal()
    hashes = list(issued.hashes)
    hashes[3] = ""  # a burned code
    assert recovery.verify(PEPPER, codes[3], hashes) is None
    assert recovery.verify(PEPPER, codes[2], hashes) == 2
    for garbage in ("", "short", "!" * 16, "A" * 17, "0189-0189-0189-0189", None):
        assert recovery.verify(PEPPER, garbage, hashes) is None
    assert recovery.verify(PEPPER, codes[0], []) is None
