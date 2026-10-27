"""The archive is untrusted: hostile ones are refused, with a stable code,
before anything is built."""

import io
import json
import stat
import time
import warnings
import zipfile

import pytest

from backend.app.services.open_formulieren import limits
from backend.app.services.open_formulieren.archive import (
    json_depth_ok,
    read_archive,
)
from backend.app.services.open_formulieren.errors import ImportRefused
from tests.app.open_formulieren.conftest import fixture_bytes, load, make_zip


def refused(data: bytes) -> ImportRefused:
    with pytest.raises(ImportRefused) as caught:
        read_archive(data)
    return caught.value


def good(**changes):
    """The decoded fixture with some entries replaced."""
    entries = load("all-components.en.zip")
    entries.update(changes)
    return entries


def test_a_real_export_is_read():
    archive = read_archive(fixture_bytes("all-components.en.zip"))
    assert archive.version == "4.0.6"
    assert archive.form["slug"] == "sample-all-components"
    assert len(archive.steps) == 3 and len(archive.definitions) == 3
    assert archive.ignored == []


# ---------------------------------------------------------------- not a zip


@pytest.mark.parametrize(
    "data",
    [
        b"",
        b"just some text",
        b"PK\x03\x04" + b"\0" * 40,
        fixture_bytes("all-components.en.zip")[:-30],
        b"%PDF-1.7\n" + b"x" * 1000,
    ],
)
def test_a_file_that_is_not_a_zip_is_refused(data):
    assert refused(data).code == "not_a_zip"


def test_an_upload_over_the_limit_is_refused():
    error = refused(b"0" * (limits.MAX_UPLOAD_BYTES + 1))
    assert (error.status, error.code) == (413, "file_too_large")
    assert error.extra["maxBytes"] == limits.MAX_UPLOAD_BYTES


# ------------------------------------------------------------ bombs and size


def test_a_high_ratio_bomb_is_refused_while_it_is_read():
    # 300 MB of zeros is a few hundred KB compressed: well under the upload
    # limit, far over the unpacked one
    data = make_zip(good(), extra={"big.bin": b"\0" * (300 * 1024 * 1024)})
    assert len(data) < limits.MAX_UPLOAD_BYTES
    started = time.monotonic()
    assert refused(data).code == "archive_too_large"
    assert time.monotonic() - started < 5


def test_a_bomb_inside_a_known_entry_is_refused_too():
    data = make_zip(good(**{"formDefinitions.json": b" " * (300 * 1024 * 1024)}))
    assert refused(data).code == "archive_too_large"


def test_an_archive_whose_parts_add_up_past_the_total_is_refused(monkeypatch):
    monkeypatch.setattr(limits, "MAX_TOTAL_BYTES", 30_000)
    monkeypatch.setattr(limits, "MAX_ENTRY_BYTES", 20_000)
    assert refused(fixture_bytes("all-components.en.zip")).code == "archive_too_large"


def test_a_declared_size_is_not_what_decides(monkeypatch):
    """The sizes in the headers only refuse early: a header that understates
    is not believed either (the entry is counted as it is unpacked)."""
    entries = good()
    data = bytearray(make_zip(entries, deflate=False))
    # shrink the declared (uncompressed) size of the first entry in both its
    # local and its central header
    for signature, offset in ((b"PK\x03\x04", 22), (b"PK\x01\x02", 24)):
        start = data.index(signature)
        data[start + offset : start + offset + 4] = (10).to_bytes(4, "little")
    error = refused(bytes(data))
    assert error.code in {"not_a_zip", "archive_json_invalid"}


def test_many_entries_are_refused_before_the_reader_builds_them():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for number in range(20_000):
            archive.writestr(f"e{number}", b"")
    data = buffer.getvalue()
    assert len(data) < limits.MAX_UPLOAD_BYTES
    started = time.monotonic()
    assert refused(data).code == "archive_too_large"
    assert time.monotonic() - started < 2


def _zip64_disguised(entries: int) -> bytes:
    """An archive of ``entries`` empty files whose plain end record claims one
    small entry while a zip64 record (reached through a locator) holds the
    real counts: the zip reader believes the zip64 record."""
    import struct

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for number in range(entries):
            archive.writestr(f"e{number}", b"")
    data = buffer.getvalue()
    start = data.rfind(b"PK\x05\x06")
    _, _, _, _, count, size, offset, _ = struct.unpack("<4s4H2LH", data[start : start + 22])
    record = struct.pack("<4sQ2H2L4Q", b"PK\x06\x06", 44, 45, 45, 0, 0, count, count, size, offset)
    locator = struct.pack("<4sLQL", b"PK\x06\x07", 0, start, 1)
    plain = struct.pack("<4s4H2LH", b"PK\x05\x06", 0, 0, 1, 1, 46 + 2, offset, 0)
    return data[:start] + record + locator + plain


def test_a_zip64_record_cannot_hide_the_entry_count():
    data = _zip64_disguised(3000)
    # what the reader would do with it: build a record for every entry
    assert len(zipfile.ZipFile(io.BytesIO(data)).namelist()) == 3000
    started = time.monotonic()
    error = refused(data)
    assert (error.code, error.status) == ("archive_unsafe", 400)
    assert time.monotonic() - started < 0.5


def test_more_entries_than_an_export_has_are_refused():
    extra = {f"note{n}.txt": b"x" for n in range(limits.MAX_ENTRIES)}
    assert refused(make_zip(good(), extra=extra)).code == "archive_too_large"


# ------------------------------------------------------------------ entries


def _with_entry(info: zipfile.ZipInfo, data: bytes = b"x", *, base=None) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, value in (base if base is not None else good()).items():
            archive.writestr(name, json.dumps(value))
        archive.writestr(info, data)
    return buffer.getvalue()


@pytest.mark.parametrize(
    "name",
    ["../x", "a/../../x", "/etc/passwd", "C:\\x", "C:/x", "a\\b", "..", "a\x01"],
)
def test_unsafe_entry_names_are_refused(name):
    assert refused(_with_entry(zipfile.ZipInfo(name))).code == "archive_unsafe"


def test_a_name_with_a_nul_byte_is_cut_by_the_reader_and_never_used():
    # Python's reader cuts a name at a NUL: "x" is then just an unknown file
    data = _with_entry(zipfile.ZipInfo("xQy")).replace(b"xQy", b"x\x00y")
    assert data.count(b"x\x00y") == 2
    assert read_archive(data).ignored == ["x"]


def test_a_known_name_hidden_behind_a_nul_byte_is_a_duplicate():
    data = _with_entry(zipfile.ZipInfo("forms.jsonQ.png")).replace(
        b"forms.jsonQ.png", b"forms.json\x00.png"
    )
    assert refused(data).code == "archive_unsafe"


def test_an_absolute_name_is_refused_even_when_named_like_a_known_file():
    info = zipfile.ZipInfo("/forms.json")
    assert refused(_with_entry(info)).code == "archive_unsafe"


def test_a_symlink_is_refused():
    info = zipfile.ZipInfo("link")
    info.create_system = 3
    info.external_attr = (stat.S_IFLNK | 0o777) << 16
    assert refused(_with_entry(info, b"/etc/passwd")).code == "archive_unsafe"


def test_a_symlink_named_like_a_known_file_is_refused():
    info = zipfile.ZipInfo("formLogic.json")
    info.create_system = 3
    info.external_attr = (stat.S_IFLNK | 0o777) << 16
    entries = good()
    del entries["formLogic.json"]
    assert refused(_with_entry(info, b"/etc/passwd", base=entries)).code == (
        "archive_unsafe"
    )


@pytest.mark.parametrize("mode", [stat.S_IFCHR, stat.S_IFBLK, stat.S_IFIFO, stat.S_IFSOCK])
def test_a_special_file_is_refused(mode):
    info = zipfile.ZipInfo("dev")
    info.create_system = 3
    info.external_attr = (mode | 0o600) << 16
    assert refused(_with_entry(info)).code == "archive_unsafe"


def test_duplicate_entry_names_are_refused():
    buffer = io.BytesIO()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        with zipfile.ZipFile(buffer, "w") as archive:
            for name, value in good().items():
                archive.writestr(name, json.dumps(value))
            archive.writestr("forms.json", json.dumps([{"name": "other"}]))
    assert refused(buffer.getvalue()).code == "archive_unsafe"


def test_an_encrypted_entry_is_refused():
    data = bytearray(make_zip(good()))
    start = data.index(b"PK\x01\x02")
    data[start + 8] |= 0x01  # general purpose flag: encrypted
    assert refused(bytes(data)).code == "archive_unsafe"


@pytest.mark.parametrize("method", [zipfile.ZIP_BZIP2, zipfile.ZIP_LZMA])
def test_an_unusual_compression_is_refused(method):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", method) as archive:
        for name, value in good().items():
            archive.writestr(name, json.dumps(value))
    assert refused(buffer.getvalue()).code == "archive_unsafe"


def test_other_safe_entries_are_ignored_and_listed():
    data = make_zip(
        good(),
        extra={"notes.txt": b"hello", "__MACOSX/._forms.json": b"junk", "dir/": b""},
    )
    archive = read_archive(data)
    assert archive.ignored == ["notes.txt", "__MACOSX/._forms.json"]
    assert archive.form["slug"] == "sample-all-components"


def test_a_known_name_in_a_folder_is_not_read():
    entries = {f"export/{name}": value for name, value in good().items()}
    error = refused(make_zip(entries))
    assert error.code == "archive_incomplete"
    assert set(error.extra["missing"]) == {
        "forms.json",
        "formSteps.json",
        "formDefinitions.json",
        "_meta.json",
    }


@pytest.mark.parametrize("name", ["forms.json", "formSteps.json", "formDefinitions.json", "_meta.json"])
def test_a_missing_required_file_is_named(name):
    entries = good()
    del entries[name]
    error = refused(make_zip(entries))
    assert (error.code, error.extra["missing"]) == ("archive_incomplete", [name])


def test_logic_and_variables_may_be_missing():
    entries = good()
    del entries["formLogic.json"], entries["formVariables.json"]
    archive = read_archive(make_zip(entries))
    assert archive.logic == [] and archive.variables == []


# --------------------------------------------------------------------- JSON


def test_deep_nesting_is_refused():
    deep = ("[" * 100 + "]" * 100).encode()
    error = refused(make_zip(good(**{"formSteps.json": deep})))
    assert (error.code, error.extra["file"]) == ("archive_json_invalid", "formSteps.json")


def test_extreme_nesting_never_reaches_the_parser():
    deep = b"[" * 2_000_000 + b"]" * 2_000_000
    started = time.monotonic()
    error = refused(make_zip(good(**{"formDefinitions.json": deep})))
    assert error.code == "archive_json_invalid"
    assert time.monotonic() - started < 5


def test_nesting_inside_the_limit_is_read():
    ok = ("[" * limits.MAX_JSON_DEPTH + "]" * limits.MAX_JSON_DEPTH).encode()
    assert json_depth_ok(ok)
    assert not json_depth_ok(b"[" + ok + b"]")


def test_brackets_in_strings_are_not_nesting():
    text = json.dumps(["[" * 500, "{" * 500, 'quote " and \\" escapes ]]]]'])
    assert json_depth_ok(text.encode())


def test_a_string_that_never_ends_is_refused_fast():
    """One lone quote followed by escaped quotes would make a naive scan
    retry at every one of them."""
    raw = b'["' + b'\\"' * 3_000_000
    started = time.monotonic()
    assert not json_depth_ok(raw)
    assert time.monotonic() - started < 2


@pytest.mark.parametrize(
    "raw",
    [b"not json", b"{", b"[1, 2,]", b"\xff\xfe", b'{"a": NaN}', b"[Infinity]", b"[1e999]"],
)
def test_invalid_json_is_refused(raw):
    error = refused(make_zip(good(**{"formLogic.json": raw})))
    assert (error.code, error.extra["file"]) == ("archive_json_invalid", "formLogic.json")


def test_a_json_entry_over_its_limit_is_refused(monkeypatch):
    monkeypatch.setattr(limits, "MAX_ENTRY_BYTES", 10_000)
    error = refused(fixture_bytes("all-components.en.zip"))
    assert error.code == "archive_too_large"


def test_too_many_json_values_are_refused(monkeypatch):
    monkeypatch.setattr(limits, "MAX_JSON_NODES", 100)
    assert refused(fixture_bytes("all-components.en.zip")).code == "archive_json_invalid"


@pytest.mark.parametrize(
    "entry, value",
    [
        ("forms.json", {"not": "a list"}),
        ("formSteps.json", [1, 2, 3]),
        ("formDefinitions.json", "text"),
        ("formLogic.json", {"a": 1}),
        ("formVariables.json", [[]]),
        ("_meta.json", [1]),
    ],
)
def test_the_wrong_shape_is_refused(entry, value):
    error = refused(make_zip(good(**{entry: value})))
    assert (error.code, error.extra["file"]) == ("archive_json_invalid", entry)


def test_the_archive_must_hold_exactly_one_form():
    forms = load("all-components.en.zip")["forms.json"]
    for value in ([], forms + forms):
        assert refused(make_zip(good(**{"forms.json": value}))).code == (
            "archive_not_a_single_form"
        )


def test_a_form_with_too_many_steps_is_too_complex():
    steps = [{"index": n} for n in range(limits.MAX_STEPS + 1)]
    error = refused(make_zip(good(**{"formSteps.json": steps})))
    assert (error.status, error.code) == (422, "archive_too_complex")


# ----------------------------------------------------------------- versions


def meta(release, **extra):
    return {"of_release": release, "of_git_sha": "x", "created": "2026-01-01", **extra}


@pytest.mark.parametrize("release", ["4.0.0", "4.0.6", "4.0.99"])
def test_the_accepted_series_is_read(release):
    assert read_archive(make_zip(good(**{"_meta.json": meta(release)}))).version == release


@pytest.mark.parametrize("release", ["4.1.0", "4.3.0", "5.0.0", "3.2.1", "2.0.0", "0.0.1"])
def test_another_release_is_refused_naming_it(release):
    error = refused(make_zip(good(**{"_meta.json": meta(release)})))
    assert (error.status, error.code) == (400, "open_formulieren_version_unsupported")
    assert error.extra == {"version": release, "supported": ["4.0"]}
    assert release in error.message


@pytest.mark.parametrize(
    "value",
    [None, "", "latest", "4.0", "4", "4.0.6-alpha.1", "4.0.6+local", "v4.0.6", 4.06, ["4.0.6"], "4.0.6\n", "<b>4.0.6</b>"],
)
def test_an_unreadable_release_is_unknown_and_never_echoed(value):
    error = refused(make_zip(good(**{"_meta.json": meta(value)})))
    assert error.code == "open_formulieren_version_unknown"
    assert "version" not in error.extra
    assert str(value) not in error.message or value in ("", None)


def test_a_missing_release_key_is_unknown():
    error = refused(make_zip(good(**{"_meta.json": {"created": "x"}})))
    assert error.code == "open_formulieren_version_unknown"
