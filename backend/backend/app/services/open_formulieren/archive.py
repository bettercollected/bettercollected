"""Read an Open Formulieren export archive safely.

The upload is untrusted. This module turns its bytes into plain JSON values
(dicts, lists, strings, numbers) or refuses it, and does nothing else:

* the archive is read in memory, never extracted, and no entry name is ever
  used as a path;
* only the six known entry names are read; any other safe name is ignored and
  listed, an unsafe one (absolute, ``..``, a drive letter, a backslash, a
  symlink or other special file, a duplicate, an encrypted entry, an
  unusual compression) refuses the archive;
* sizes are enforced while reading, with streaming caps: what the archive
  declares is used only to refuse early, never to allow;
* the central directory is bounded before the zip reader parses it (it builds
  one record per entry before we could count them), and an archive with a
  zip64 locator is refused (the reader would take its counts from a zip64
  record the bound does not see; an export of one form is never that large);
* a JSON entry is checked for nesting depth by an iterative scan before it is
  parsed (the stdlib parser recurses), non-finite numbers are refused, and the
  parsed value is counted;
* nothing from the file is executed or evaluated.
"""

from __future__ import annotations

import io
import json
import math
import re
import stat
import struct
import zipfile
from dataclasses import dataclass, field
from http import HTTPStatus
from typing import Any, Dict, List, Optional, Tuple

from backend.app.services.open_formulieren import limits
from backend.app.services.open_formulieren.errors import refuse
from backend.app.services.open_formulieren.mapping import (
    ENTRY_FORM,
    ENTRY_LOGIC,
    ENTRY_META,
    ENTRY_STEPS,
    ENTRY_DEFINITIONS,
    ENTRY_VARIABLES,
    KNOWN_ENTRIES,
    REQUIRED_ENTRIES,
)

_EOCD = b"PK\x05\x06"
_ZIP64_LOCATOR = b"PK\x06\x07"
_ZIP64_LOCATOR_SIZE = 20
_EOCD_STRUCT = struct.Struct("<4s4H2LH")
_ALLOWED_COMPRESSION = {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}
_DRIVE = re.compile(r"^[A-Za-z]:")
# ASCII digits only (``\d`` also matches other scripts' digits) and no leading
# zeros: a real release never has them
_VERSION = re.compile(r"^(0|[1-9][0-9]{0,3})\.(0|[1-9][0-9]{0,3})\.(0|[1-9][0-9]{0,5})$")


@dataclass
class Archive:
    """The decoded export: plain JSON values."""

    version: str
    series: Tuple[int, int]
    meta: Dict[str, Any]
    form: Dict[str, Any]
    steps: List[Dict[str, Any]]
    definitions: List[Dict[str, Any]]
    logic: List[Dict[str, Any]]
    variables: List[Dict[str, Any]]
    # names of safe entries that were not read (never an unsafe name)
    ignored: List[str] = field(default_factory=list)

    @property
    def is_3x(self) -> bool:
        """Whether the export comes from the 3.x series, whose format differs
        from 4.0's in a few places (docs/open-formulieren.md)."""
        return self.series[0] == limits.LEGACY_MAJOR


# ---------------------------------------------------------------- zip layer


def _central_directory_check(data: bytes) -> None:
    """Refuse an archive whose central directory is bigger than sixteen
    entries can need, before the zip reader builds a record for each of
    them. Mirrors where the reader looks for the end-of-directory record."""
    record: Optional[bytes] = None
    start = -1
    tail = data[-_EOCD_STRUCT.size :]
    if len(tail) == _EOCD_STRUCT.size and tail[:4] == _EOCD and tail[-2:] == b"\0\0":
        record = tail
        start = len(data) - _EOCD_STRUCT.size
    else:
        start = data.rfind(_EOCD, max(0, len(data) - (1 << 16) - _EOCD_STRUCT.size))
        if start >= 0 and len(data) - start >= _EOCD_STRUCT.size:
            record = data[start : start + _EOCD_STRUCT.size]
    if record is None:
        raise refuse("not_a_zip", "The file is not a zip archive.")
    # a zip64 locator just before the record makes the reader take its counts
    # from a zip64 record instead, which this check does not see: an export of
    # one form is never that large, so zip64 is never legitimate here
    if data[max(0, start - _ZIP64_LOCATOR_SIZE) : start].startswith(_ZIP64_LOCATOR):
        raise refuse("archive_unsafe", "The archive uses a format an export never does.")
    _, _, _, _, entries, size, _, _ = _EOCD_STRUCT.unpack(record)
    # 0xFFFF / 0xFFFFFFFF: the real numbers are in a zip64 record, which an
    # export of one form never needs
    if (
        entries == 0xFFFF
        or size == 0xFFFFFFFF
        or entries > limits.MAX_ENTRIES
        or size > limits.MAX_CENTRAL_DIRECTORY_BYTES
    ):
        raise refuse(
            "archive_too_large",
            "The archive holds more files than an export of one form does.",
        )


def _unsafe_name(name: str) -> bool:
    if not name or len(name) > limits.MAX_ENTRY_NAME_LENGTH:
        return True
    if "\x00" in name or "\\" in name or name.startswith("/") or _DRIVE.match(name):
        return True
    if any(ord(c) < 32 or ord(c) == 127 for c in name):
        return True
    return any(part == ".." for part in name.split("/"))


def _check_entry(info: zipfile.ZipInfo) -> None:
    if _unsafe_name(info.filename):
        raise refuse("archive_unsafe", "The archive holds a file with an unsafe name.")
    if info.flag_bits & 0x1:
        raise refuse("archive_unsafe", "The archive holds an encrypted file.")
    if info.compress_type not in _ALLOWED_COMPRESSION:
        raise refuse("archive_unsafe", "The archive uses an unsupported compression.")
    # the Unix mode lives in the high half of external_attr when the archive
    # was made on Unix; a link or any special file is never a form export
    if info.create_system == 3:
        # (Python's own writer stores permission bits with no file type, so
        # "no type" is a plain file)
        file_type = stat.S_IFMT(info.external_attr >> 16)
        if file_type not in (0, stat.S_IFREG, stat.S_IFDIR):
            raise refuse(
                "archive_unsafe", "The archive holds a link or a special file."
            )
    if info.file_size > limits.MAX_ENTRY_BYTES:
        raise refuse("archive_too_large", "A file in the archive is too large.")


def _read_entry(zf: zipfile.ZipFile, info: zipfile.ZipInfo, budget: List[int]) -> bytes:
    """The entry's bytes, counted as they are decompressed: stops as soon as
    the entry or the archive passes its limit (a bomb never gets further than
    the cap), whatever sizes the headers declare."""
    chunks: List[bytes] = []
    size = 0
    try:
        with zf.open(info) as handle:
            while True:
                chunk = handle.read(limits.READ_CHUNK)
                if not chunk:
                    break
                size += len(chunk)
                budget[0] -= len(chunk)
                if size > limits.MAX_ENTRY_BYTES or budget[0] < 0:
                    raise refuse(
                        "archive_too_large", "The archive is too large once unpacked."
                    )
                chunks.append(chunk)
    except (zipfile.BadZipFile, EOFError, OSError, RuntimeError, NotImplementedError):
        raise refuse("not_a_zip", "The file could not be read as a zip archive.")
    return b"".join(chunks)


# --------------------------------------------------------------- json layer

# a whole string, a bracket, or a lone quote (a string that never ends)
_JSON_TOKEN = re.compile(rb'"(?:[^"\\]++|\\.)*+"|[\[\]{}]|"', re.DOTALL)


def json_depth_ok(raw: bytes, max_depth: int = limits.MAX_JSON_DEPTH) -> bool:
    """Whether ``raw`` nests arrays and objects no deeper than ``max_depth``.
    An iterative, linear scan (strings skipped), so a hostile document cannot
    exhaust the parser's stack. A string that never ends is not JSON: the
    scan stops there and says no (it would otherwise retry at every later
    quote)."""
    depth = 0
    for match in _JSON_TOKEN.finditer(raw):
        token = match.group(0)
        if token == b'"':
            return False
        if token in (b"[", b"{"):
            depth += 1
            if depth > max_depth:
                return False
        elif token in (b"]", b"}"):
            depth -= 1
    return True


def _reject_constant(name: str):
    raise ValueError(f"constant {name} is not allowed")


def _finite_float(text: str) -> float:
    value = float(text)
    if not math.isfinite(value):
        raise ValueError("number out of range")
    return value


def count_nodes(value: Any, limit: int) -> int:
    """Number of JSON values in ``value`` (iterative), stopping past
    ``limit``."""
    count = 0
    stack = [value]
    while stack:
        item = stack.pop()
        count += 1
        if count > limit:
            return count
        if isinstance(item, dict):
            stack.extend(item.values())
        elif isinstance(item, list):
            stack.extend(item)
    return count


def parse_json(raw: bytes, name: str) -> Any:
    """``raw`` as JSON, or an ``archive_json_invalid`` refusal naming the
    entry (never its content)."""

    def invalid(why: str):
        return refuse(
            "archive_json_invalid",
            f"{name} is not usable: {why}.",
            file=name,
        )

    if len(raw) > limits.MAX_ENTRY_BYTES:
        raise invalid("it is too large")
    if not json_depth_ok(raw):
        raise invalid("it is nested too deeply")
    # a cheap count before the parser builds anything: every value is
    # introduced by a bracket or a comma (those inside strings only add to it)
    if (
        raw.count(b"{") + raw.count(b"[") + raw.count(b",")
        > 2 * limits.MAX_JSON_NODES
    ):
        raise invalid("it holds too many values")
    try:
        text = raw.decode("utf-8")
        value = json.loads(
            text, parse_constant=_reject_constant, parse_float=_finite_float
        )
    except (UnicodeDecodeError, ValueError, RecursionError):
        raise invalid("it is not valid JSON")
    if count_nodes(value, limits.MAX_JSON_NODES) > limits.MAX_JSON_NODES:
        raise invalid("it is too large")
    return value


# ------------------------------------------------------------------ version


def parse_version(meta: Dict[str, Any]) -> Tuple[str, Tuple[int, int, int]]:
    """The release the export came from, as written in ``_meta.json``:
    ``(text, (major, minor, patch))``. Only a plain ``MAJOR.MINOR.PATCH`` is
    read: anything else (missing, odd text, a pre-release) is not echoed."""
    release = meta.get("of_release")
    match = _VERSION.fullmatch(release) if isinstance(release, str) else None
    if match is None:
        raise refuse(
            "open_formulieren_version_unknown",
            "The archive does not say which Open Formulieren release made it.",
        )
    return release, (int(match.group(1)), int(match.group(2)), int(match.group(3)))


def check_version(meta: Dict[str, Any]) -> Tuple[str, Tuple[int, int]]:
    """``(release text, (major, minor))`` of an accepted export, or a
    refusal that names the release."""
    text, (major, minor, _) = parse_version(meta)
    if (major, minor) not in limits.ACCEPTED_SERIES:
        raise refuse(
            "open_formulieren_version_unsupported",
            f"Exports from Open Formulieren {text} cannot be imported; "
            "this import reads releases "
            + ", ".join(f"{a}.{b}.x" for a, b in limits.ACCEPTED_SERIES)
            + ".",
            version=text,
            supported=[f"{a}.{b}" for a, b in limits.ACCEPTED_SERIES],
        )
    return text, (major, minor)


# -------------------------------------------------------------------- read


def _as_list_of_dicts(value: Any, name: str, *, exactly: Optional[int] = None):
    if not isinstance(value, list) or not all(isinstance(v, dict) for v in value):
        raise refuse(
            "archive_json_invalid",
            f"{name} is not usable: it must be a list of objects.",
            file=name,
        )
    if exactly is not None and len(value) != exactly:
        raise refuse(
            "archive_not_a_single_form",
            "The archive must hold exactly one form.",
        )
    return value


def read_archive(data: bytes) -> Archive:
    """Decode an export archive, or raise ``ImportRefused``."""
    if len(data) > limits.MAX_UPLOAD_BYTES:
        raise refuse(
            "file_too_large",
            "The file is too large.",
            HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
            maxBytes=limits.MAX_UPLOAD_BYTES,
        )
    _central_directory_check(data)
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except (
        zipfile.BadZipFile,
        zipfile.LargeZipFile,
        EOFError,
        OSError,
        ValueError,
        NotImplementedError,
    ):
        raise refuse("not_a_zip", "The file is not a zip archive.")
    with zf:
        infos = zf.infolist()
        if len(infos) > limits.MAX_ENTRIES:
            raise refuse(
                "archive_too_large",
                "The archive holds more files than an export of one form does.",
            )
        names = [i.filename for i in infos]
        if len(set(names)) != len(names):
            raise refuse(
                "archive_unsafe", "The archive holds two files with the same name."
            )
        declared = 0
        for info in infos:
            _check_entry(info)
            declared += info.file_size
        if declared > limits.MAX_TOTAL_BYTES:
            raise refuse("archive_too_large", "The archive is too large once unpacked.")

        budget = [limits.MAX_TOTAL_BYTES]
        raw: Dict[str, bytes] = {}
        ignored: List[str] = []
        for info in infos:
            name = info.filename
            if name in KNOWN_ENTRIES:
                raw[name] = _read_entry(zf, info, budget)
            elif not name.endswith("/"):
                ignored.append(name)

    missing = [name for name in REQUIRED_ENTRIES if name not in raw]
    if missing:
        raise refuse(
            "archive_incomplete",
            "The archive is not an Open Formulieren export: it lacks "
            + ", ".join(missing)
            + ".",
            missing=missing,
        )

    meta = parse_json(raw[ENTRY_META], ENTRY_META)
    if not isinstance(meta, dict):
        raise refuse(
            "archive_json_invalid",
            f"{ENTRY_META} is not usable: it must be an object.",
            file=ENTRY_META,
        )
    version, series = check_version(meta)

    forms = _as_list_of_dicts(
        parse_json(raw[ENTRY_FORM], ENTRY_FORM), ENTRY_FORM, exactly=1
    )
    steps = _as_list_of_dicts(parse_json(raw[ENTRY_STEPS], ENTRY_STEPS), ENTRY_STEPS)
    definitions = _as_list_of_dicts(
        parse_json(raw[ENTRY_DEFINITIONS], ENTRY_DEFINITIONS), ENTRY_DEFINITIONS
    )
    logic = _as_list_of_dicts(
        parse_json(raw[ENTRY_LOGIC], ENTRY_LOGIC) if ENTRY_LOGIC in raw else [],
        ENTRY_LOGIC,
    )
    variables = _as_list_of_dicts(
        parse_json(raw[ENTRY_VARIABLES], ENTRY_VARIABLES)
        if ENTRY_VARIABLES in raw
        else [],
        ENTRY_VARIABLES,
    )
    if (
        len(steps) > limits.MAX_STEPS
        or len(logic) > limits.MAX_LOGIC_RULES
        or len(variables) > limits.MAX_VARIABLES
    ):
        raise refuse(
            "archive_too_complex",
            "The form has more steps, rules or variables than can be imported.",
            HTTPStatus.UNPROCESSABLE_ENTITY,
        )
    return Archive(
        version=version,
        series=series,
        meta=meta,
        form=forms[0],
        steps=steps,
        definitions=definitions,
        logic=logic,
        variables=variables,
        ignored=ignored,
    )
