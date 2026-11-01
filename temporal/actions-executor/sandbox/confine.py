"""Operating-system confinement of the sandbox child, applied by the child itself
(``child.py``) before it reads any code.

Nothing here needs a container flag, a profile file or an orchestrator feature:
it is the Linux kernel's own per-process mechanisms, so it is the same on a
compose stack, on Docker Swarm (whose stack files ignore ``network_mode`` and
``security_opt``) and on a bare host. The container's own hardening (internal
network, dropped capabilities, read-only root, limits) comes on top of it and
is documented in docs/executor-isolation.md, but nothing depends on it.

In order:

1. every inherited file descriptor except stdin and stdout is closed;
2. resource limits: address space, CPU seconds, no file larger than zero bytes
   (nothing can be written), few open files, no core dump;
3. the filesystem is cut away: ``chroot`` into an empty scratch directory and a
   drop to an unprivileged user and group when the child starts as root (the
   executor image runs as root), and a Landlock ruleset that allows no
   filesystem access at all whenever the kernel has Landlock. The child imports
   everything it will ever need *before* this, so it needs no file after it;
4. ``no_new_privs`` and a non-dumpable process;
5. a seccomp filter (installed by this module with ``prctl``, no library
   needed) that makes the system calls in ``syscalls.DENIED`` fail with EPERM:
   no socket of any kind, no ``execve``, no ``fork``/``clone``, no signals to
   other processes, no ``ptrace``, no mounts or namespaces, no changes to the
   filesystem, and ``open`` only read-only.

``apply`` returns what actually took effect; the broker refuses to send code to a
child that did not confine itself as required.
"""

import ctypes
import os
import resource
import struct
from typing import Dict, List, Optional, Tuple

from sandbox.syscalls import DENIED, OPEN

UNPRIVILEGED_ID = 65534

# prctl
PR_SET_DUMPABLE = 4
PR_SET_NO_NEW_PRIVS = 38
PR_SET_SECCOMP = 22
SECCOMP_MODE_FILTER = 2

# seccomp return values
RET_ALLOW = 0x7FFF0000
RET_KILL_PROCESS = 0x80000000
RET_ERRNO = 0x00050000
EPERM = 1

AUDIT_ARCH = {"x86_64": 0xC000003E, "aarch64": 0xC00000B7}
X32_SYSCALL_BIT = 0x40000000

# BPF
LD_W_ABS = 0x20
JEQ_K = 0x15
JGE_K = 0x35
JSET_K = 0x45
RET_K = 0x06

# open(2) flags that ask to write or to create
O_WRONLY, O_RDWR, O_CREAT, O_TRUNC, O_APPEND = 0o1, 0o2, 0o100, 0o1000, 0o2000
O_TMPFILE_BIT = 0o20000000  # __O_TMPFILE (O_TMPFILE also holds O_DIRECTORY)
WRITE_FLAGS = O_WRONLY | O_RDWR | O_CREAT | O_TRUNC | O_APPEND | O_TMPFILE_BIT

# Landlock
SYS_LANDLOCK_CREATE_RULESET = 444
SYS_LANDLOCK_RESTRICT_SELF = 446
LANDLOCK_CREATE_RULESET_VERSION = 1


class ConfinementError(Exception):
    """A required confinement step could not be applied."""


def machine() -> str:
    arch = os.uname().machine.lower()
    return {"amd64": "x86_64", "arm64": "aarch64"}.get(arch, arch)


# ---- seccomp ----------------------------------------------------------------


def _insn(code: int, jt: int, jf: int, k: int) -> bytes:
    return struct.pack("<HBBI", code, jt, jf, k)


def build_filter(arch: Optional[str] = None) -> bytes:
    """The BPF program (``struct sock_filter`` array) for ``arch``."""
    arch = arch or machine()
    if arch not in AUDIT_ARCH:
        raise ConfinementError(f"no seccomp filter for the {arch} architecture")
    denied = sorted(
        {numbers[arch] for _name, _group, numbers in DENIED if arch in numbers}
    )
    open_numbers = OPEN[arch]

    # symbolic program: (code, jt_label, jf_label, k); a label is a name or None
    program: List[Tuple[int, Optional[str], Optional[str], int]] = []
    labels: Dict[str, int] = {}

    def emit(code, jt=None, jf=None, k=0):
        program.append((code, jt, jf, k))

    def label(name):
        labels[name] = len(program)

    # the architecture must be the one the table is for (no 32-bit entry)
    emit(LD_W_ABS, k=4)  # seccomp_data.arch
    emit(JEQ_K, jt="arch_ok", jf="kill", k=AUDIT_ARCH[arch])
    label("kill")
    emit(RET_K, k=RET_KILL_PROCESS)
    label("arch_ok")
    emit(LD_W_ABS, k=0)  # seccomp_data.nr
    if arch == "x86_64":
        # the x32 ABI numbers its calls from 0x40000000: not a way around the list
        emit(JGE_K, jt="deny", jf=None, k=X32_SYSCALL_BIT)
    for number in denied:
        emit(JEQ_K, jt="deny", jf=None, k=number)
    # open / openat: refused only when the flags ask to write or create
    for name, flags_arg in (("open", 1), ("openat", 2)):
        if name in open_numbers:
            emit(JEQ_K, jt=f"flags_{name}", jf=None, k=open_numbers[name])
    emit(RET_K, k=RET_ALLOW)
    for name, flags_arg in (("open", 1), ("openat", 2)):
        if name in open_numbers:
            label(f"flags_{name}")
            emit(LD_W_ABS, k=16 + 8 * flags_arg)  # low word of args[flags_arg]
            emit(JSET_K, jt="deny", jf="allow", k=WRITE_FLAGS)
    label("allow")
    emit(RET_K, k=RET_ALLOW)
    label("deny")
    emit(RET_K, k=RET_ERRNO | EPERM)

    out = bytearray()
    for index, (code, jt, jf, k) in enumerate(program):

        def offset(target):
            if target is None:
                return 0
            distance = labels[target] - index - 1
            if not 0 <= distance <= 255:
                raise ConfinementError("seccomp filter jump out of range")
            return distance

        out += _insn(code, offset(jt), offset(jf), k)
    return bytes(out)


def _libc():
    """libc with explicit argument types: ctypes passes a plain Python int to a
    variadic function as a C int, which would cut an address to 32 bits."""
    libc = ctypes.CDLL(None, use_errno=True)
    libc.prctl.argtypes = [ctypes.c_int] + [ctypes.c_ulong] * 4
    libc.prctl.restype = ctypes.c_int
    libc.syscall.argtypes = [ctypes.c_long] + [ctypes.c_ulong] * 3
    libc.syscall.restype = ctypes.c_long
    return libc


def install_seccomp() -> None:
    program = build_filter()
    count = len(program) // 8
    buffer = ctypes.create_string_buffer(program, len(program))
    # struct sock_fprog { unsigned short len; struct sock_filter *filter; }
    header = struct.pack(
        "@HP", count, ctypes.addressof(buffer)
    )  # native padding between the fields
    prog = ctypes.create_string_buffer(header, len(header))
    libc = _libc()
    if libc.prctl(PR_SET_SECCOMP, SECCOMP_MODE_FILTER, ctypes.addressof(prog), 0, 0):
        raise ConfinementError(f"seccomp: errno {ctypes.get_errno()}")


def _syscall(libc, number: int, *args: int) -> int:
    padded = list(args) + [0] * (3 - len(args))
    return libc.syscall(number, *padded)


# ---- filesystem -------------------------------------------------------------


def landlock_abi() -> int:
    """The kernel's Landlock ABI version, 0 when there is none."""
    libc = _libc()
    result = _syscall(
        libc, SYS_LANDLOCK_CREATE_RULESET, 0, 0, LANDLOCK_CREATE_RULESET_VERSION
    )
    return int(result) if result > 0 else 0


def deny_all_filesystem_access() -> bool:
    """Restrict this process (and what it starts) to no filesystem access:
    a ruleset that handles every file access right and holds no rule. Files
    already open stay usable. False when the kernel has no Landlock."""
    abi = landlock_abi()
    if abi < 1:
        return False
    rights = (1 << 13) - 1  # ABI 1: execute .. make_sym
    if abi >= 2:
        rights |= 1 << 13  # refer
    if abi >= 3:
        rights |= 1 << 14  # truncate
    if abi >= 5:
        rights |= 1 << 15  # ioctl on devices
    attr = ctypes.create_string_buffer(struct.pack("<Q", rights), 8)
    libc = _libc()
    fd = _syscall(libc, SYS_LANDLOCK_CREATE_RULESET, ctypes.addressof(attr), 8, 0)
    if fd < 0:
        return False
    try:
        if _syscall(libc, SYS_LANDLOCK_RESTRICT_SELF, fd, 0):
            return False
    finally:
        os.close(fd)
    return True


def _chroot_and_drop(scratch: str) -> bool:
    """Only for a child that starts as root: into the empty scratch directory
    as an unprivileged user. False (nothing changed) for any other user."""
    if os.geteuid() != 0:
        return False
    os.chroot(scratch)
    os.chdir("/")
    os.setgroups([])
    os.setresgid(UNPRIVILEGED_ID, UNPRIVILEGED_ID, UNPRIVILEGED_ID)
    os.setresuid(UNPRIVILEGED_ID, UNPRIVILEGED_ID, UNPRIVILEGED_ID)
    try:
        os.setuid(0)
    except PermissionError:
        return True
    raise ConfinementError("the child could not give up root")


# ---- the whole thing ----------------------------------------------------------


def apply(memory_mb: int, cpu_seconds: int, scratch: str) -> Dict[str, object]:
    """Confine this process. Returns the facts the broker checks."""
    facts: Dict[str, object] = {"arch": machine()}
    os.closerange(3, 1 << 16)

    memory = int(memory_mb) * 1024 * 1024
    resource.setrlimit(resource.RLIMIT_AS, (memory, memory))
    resource.setrlimit(resource.RLIMIT_CPU, (int(cpu_seconds), int(cpu_seconds) + 2))
    resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_NOFILE, (32, 32))
    facts["rlimits"] = True

    filesystem = []
    if _chroot_and_drop(scratch):
        filesystem.append("chroot")
        facts["unprivileged"] = os.getuid() == UNPRIVILEGED_ID
    else:
        facts["unprivileged"] = os.geteuid() != 0
    libc = _libc()
    libc.prctl(PR_SET_DUMPABLE, 0, 0, 0, 0)
    if libc.prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0):
        raise ConfinementError("no_new_privs")
    facts["no_new_privs"] = True
    if deny_all_filesystem_access():
        filesystem.append("landlock")
    facts["filesystem"] = "+".join(filesystem) or "none"

    try:
        install_seccomp()
        facts["seccomp"] = True
    except ConfinementError:
        facts["seccomp"] = False
    return facts
