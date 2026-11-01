"""The seccomp filter, evaluated without installing it: a small BPF interpreter
runs ``confine.build_filter`` for each architecture on (architecture, number,
arguments), so every denied call, the x32 ABI, a foreign architecture and the
read-only ``open`` rule are checked on any machine. Numbers are checked against
the kernel headers when they are installed."""

import os
import re
import struct

import pytest

from sandbox import confine
from sandbox.syscalls import ARG_DENIED, DENIED, OPEN

ALLOW, KILL, EPERM = confine.RET_ALLOW, confine.RET_KILL_PROCESS, confine.RET_ERRNO | 1
ARCHES = ("x86_64", "aarch64")

# x86_64 numbers of calls that must stay allowed (what Python needs once running)
ALLOWED_X86_64 = {
    "read": 0,
    "write": 1,
    "close": 3,
    "fstat": 5,
    "mmap": 9,
    "mprotect": 10,
    "munmap": 11,
    "brk": 12,
    "rt_sigaction": 13,
    "rt_sigprocmask": 14,
    "madvise": 28,
    "getpid": 39,
    "exit": 60,
    "getrandom": 318,
    "futex": 202,
    "clock_gettime": 228,
    "exit_group": 231,
}


def run_filter(program: bytes, arch: int, number: int, args=(0,) * 6) -> int:
    """Evaluate a classic BPF seccomp program (the instructions the filter uses)."""
    data = struct.pack("<IIQ6Q", number, arch, 0, *args)
    instructions = [
        struct.unpack_from("<HBBI", program, offset)
        for offset in range(0, len(program), 8)
    ]
    accumulator, pc = 0, 0
    while True:
        code, jt, jf, k = instructions[pc]
        pc += 1
        if code == confine.LD_W_ABS:
            (accumulator,) = struct.unpack_from("<I", data, k)
        elif code == confine.JEQ_K:
            pc += jt if accumulator == k else jf
        elif code == confine.JGE_K:
            pc += jt if accumulator >= k else jf
        elif code == confine.JSET_K:
            pc += jt if accumulator & k else jf
        elif code == confine.RET_K:
            return k
        else:
            raise AssertionError(f"unknown instruction {code:#x}")


@pytest.mark.parametrize("arch", ARCHES)
def test_every_denied_call_fails_with_eperm(arch):
    program = confine.build_filter(arch)
    audit = confine.AUDIT_ARCH[arch]
    seen = 0
    for name, _group, numbers in DENIED:
        if arch in numbers:
            assert run_filter(program, audit, numbers[arch]) == EPERM, name
            seen += 1
    assert seen > 100


@pytest.mark.parametrize("arch", ARCHES)
def test_the_calls_that_set_signals_or_limits_of_others_are_denied(arch):
    names = {name for name, _g, numbers in DENIED if arch in numbers}
    assert {
        "kill",
        "tkill",
        "tgkill",
        "rt_sigqueueinfo",
        "rt_tgsigqueueinfo",
        "pidfd_send_signal",
        "prlimit64",
        "setpriority",
        "sched_setscheduler",
        "sched_setaffinity",
        "ioprio_set",
        "process_madvise",
        "kcmp",
        "syslog",
        "shmget",
        "msgget",
        "semget",
        "mq_open",
        "memfd_secret",
    } <= names


def test_a_foreign_architecture_is_killed_and_x32_is_refused():
    program = confine.build_filter("x86_64")
    # the 32-bit x86 and arm64 entry points are not the table's architecture
    assert run_filter(program, 0x40000003, 4) == KILL
    assert run_filter(program, confine.AUDIT_ARCH["aarch64"], 63) == KILL
    # the x32 ABI numbers its calls from 0x40000000: not a way round the list
    assert run_filter(program, confine.AUDIT_ARCH["x86_64"], 0x40000000 | 0) == EPERM
    assert run_filter(program, confine.AUDIT_ARCH["x86_64"], 0x40000000 | 41) == EPERM
    aarch64 = confine.build_filter("aarch64")
    assert run_filter(aarch64, confine.AUDIT_ARCH["x86_64"], 0) == KILL


def test_an_unknown_architecture_has_no_filter():
    with pytest.raises(confine.ConfinementError):
        confine.build_filter("riscv64")


def test_what_python_needs_after_it_started_stays_allowed():
    program = confine.build_filter("x86_64")
    for name, number in ALLOWED_X86_64.items():
        assert run_filter(program, confine.AUDIT_ARCH["x86_64"], number) == ALLOW, name


@pytest.mark.parametrize("arch", ARCHES)
def test_open_is_refused_only_when_it_asks_to_write_or_create(arch):
    program = confine.build_filter(arch)
    audit = confine.AUDIT_ARCH[arch]
    for name, flags_index in (("open", 1), ("openat", 2)):
        if name not in OPEN[arch]:
            continue
        number = OPEN[arch][name]

        def call(flags):
            args = [0] * 6
            args[flags_index] = flags
            return run_filter(program, audit, number, args)

        assert call(0) == ALLOW  # O_RDONLY
        assert call(0o200000) == ALLOW  # O_RDONLY | O_DIRECTORY
        assert call(0o2000000) == ALLOW  # O_RDONLY | O_CLOEXEC
        for flag in (
            confine.O_WRONLY,
            confine.O_RDWR,
            confine.O_CREAT,
            confine.O_TRUNC,
            confine.O_APPEND,
            confine.O_TMPFILE_BIT,
            confine.O_WRONLY | confine.O_CREAT | confine.O_TRUNC,
        ):
            assert call(flag) == EPERM, (name, flag)
        # only the low word is the flags: a high word in the register is not
        high = [0] * 6
        high[flags_index] = 1 << 33
        assert run_filter(program, audit, number, high) == ALLOW


@pytest.mark.parametrize("arch", ARCHES)
def test_fcntl_and_ioctl_cannot_make_another_process_a_signal_target(arch):
    program = confine.build_filter(arch)
    audit = confine.AUDIT_ARCH[arch]
    numbers = {name: nums[arch] for name, _arg, _values, nums in ARG_DENIED}

    def call(name, command, high=0):
        return run_filter(program, audit, numbers[name], [3, command | high, 0, 0, 0, 0])

    for command in (8, 15, 10):  # F_SETOWN, F_SETOWN_EX, F_SETSIG
        assert call("fcntl", command) == EPERM, command
        # the kernel reads the low 32 bits of the command: so does the filter
        assert call("fcntl", command, high=1 << 33) == EPERM, command
    for command in (0x8901, 0x8902):  # FIOSETOWN, SIOCSPGRP
        assert call("ioctl", command) == EPERM, command
    # what Python itself uses stays allowed
    for command in (0, 1, 2, 3, 4, 9):  # F_DUPFD, F_GETFD, F_SETFD, F_GETFL, F_SETFL, F_GETOWN
        assert call("fcntl", command) == ALLOW, command
    assert call("ioctl", 0x5401) == ALLOW  # TCGETS


def test_the_filter_fits_in_one_jump_range():
    for arch in ARCHES:
        assert len(confine.build_filter(arch)) // 8 < 255 * 2


def _header_numbers(path):
    numbers = {}
    for line in open(path):
        match = re.match(r"#define __NR_(\w+)\s+(\d+)\s*$", line)
        if match:
            numbers[match.group(1)] = int(match.group(2))
    return numbers


X86_HEADER = "/usr/include/x86_64-linux-gnu/asm/unistd_64.h"
GENERIC_HEADER = "/usr/include/asm-generic/unistd.h"


@pytest.mark.skipif(
    not os.path.exists(X86_HEADER), reason="kernel headers not installed"
)
def test_the_x86_64_numbers_are_the_kernels():
    header = _header_numbers(X86_HEADER)
    for name, _group, numbers in DENIED:
        if "x86_64" in numbers:
            assert header.get(name) == numbers["x86_64"], name
    assert header["open"] == OPEN["x86_64"]["open"]
    assert header["openat"] == OPEN["x86_64"]["openat"]
    for name, _arg, _values, numbers in ARG_DENIED:
        assert header.get(name) == numbers["x86_64"], name


@pytest.mark.skipif(
    not os.path.exists(GENERIC_HEADER), reason="kernel headers not installed"
)
def test_the_aarch64_numbers_are_the_generic_tables():
    header = {}
    for line in open(GENERIC_HEADER):
        match = re.match(r"#define __NR(?:3264)?_(\w+)\s+(\d+)\s*$", line)
        if match:
            header[match.group(1)] = int(match.group(2))
    for name, _group, numbers in DENIED:
        if "aarch64" in numbers:
            assert header.get(name) == numbers["aarch64"], name
    assert header["openat"] == OPEN["aarch64"]["openat"]
    for name, _arg, _values, numbers in ARG_DENIED:
        assert header.get(name) == numbers["aarch64"], name
