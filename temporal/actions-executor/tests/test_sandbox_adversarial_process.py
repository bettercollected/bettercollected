"""Adversarial suite, layer 2: the process.

Here the policy layer is switched off (``_unvalidated_for_tests``): the code
gets the real builtins, so ``import os`` works, as if a trick had got it out of
the restricted language. Everything below must still fail: the child is a
confined process with nothing to reach (docs/executor-isolation.md).

Each attempt logs ``<name>:blocked:<ErrorClass>`` when it failed, as it must,
or ``<name>:OPEN`` (and a leak marker where there is one) when it did not.
"""

import os

import pytest

from tests.sandbox_support import needs_confinement, run

pytestmark = needs_confinement

SENTINEL = "SENTINEL-THE-EXECUTOR-KEY-0123456789"


@pytest.fixture(autouse=True)
def executor_secrets(monkeypatch):
    # what the executor process holds: none of it may reach the child
    monkeypatch.setenv("AES_HEX_KEY", SENTINEL)
    monkeypatch.setenv("API_KEY", SENTINEL)
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:" + SENTINEL + "@h/db")


def attempts(body: str, **limits):
    """Run code that defines ``attempt(name, fn)`` and calls it per line."""
    prelude = (
        # only modules the child already holds: once confined it can import no more
        "import os, sys, ctypes, json, struct\n"
        "libc = ctypes.CDLL(None, use_errno=True)\n"
        "libc.syscall.argtypes = [ctypes.c_long] + [ctypes.c_ulong] * 6\n"
        "def raw(number, *args):\n"
        "    padded = list(args) + [0] * (6 - len(args))\n"
        "    result = libc.syscall(number, *padded)\n"
        "    if result == -1:\n"
        "        raise OSError(ctypes.get_errno(), 'denied')\n"
        "    return result\n"
        "def attempt(name, fn):\n"
        "    try:\n"
        "        value = fn()\n"
        "        log(name + ':OPEN:' + str(value)[:200])\n"
        "    except BaseException as error:\n"
        "        log(name + ':blocked:' + type(error).__name__ + ':' + str(getattr(error, 'errno', '')))\n"
    )
    outcome = run(prelude + body, unvalidated=True, **limits)
    assert outcome.error is None, outcome.error
    results = dict(line.split(":", 1) for line in outcome.log)
    joined = "\n".join(outcome.log)
    assert SENTINEL not in joined
    return results


def assert_denied_by_seccomp(results, names):
    """The kernel's own answer: EPERM from the filter, not a missing file."""
    for name in names:
        result = results.get(name, "")
        assert result.startswith("blocked:") and result.endswith(
            ":1"
        ), f"{name} was {result}"


def assert_all_blocked(results, names):
    for name in names:
        assert name in results, f"{name} did not run: {results}"
        assert results[name].startswith("blocked:"), f"{name} was {results[name]}"


def test_the_child_reports_how_it_confined_itself():
    outcome = run("", unvalidated=True)
    facts = outcome.facts
    assert facts["seccomp"] is True and facts["no_new_privs"] is True
    assert facts["rlimits"] is True and facts["unprivileged"] is True
    assert facts["filesystem"] != "none"


def test_the_environment_holds_no_secret_of_the_executor():
    outcome = run(
        "import os\nlog(','.join(sorted(os.environ)))\nlog(str(os.environ))",
        unvalidated=True,
    )
    assert SENTINEL not in "\n".join(outcome.log)
    names = outcome.log[0].split(",")
    assert not {"AES_HEX_KEY", "API_KEY", "DATABASE_URL"} & set(names)


def test_files_cannot_be_read_or_written(tmp_path):
    secret = tmp_path / "secret.txt"
    secret.write_text(SENTINEL)
    results = attempts(
        f"""
attempt("read_a_file", lambda: open({str(secret)!r}).read())
attempt("read_passwd", lambda: open("/etc/passwd").read())
attempt("read_proc_environ_of_the_executor", lambda: open("/proc/%d/environ" % os.getppid()).read())
attempt("read_proc_mem_of_the_executor", lambda: open("/proc/%d/mem" % os.getppid(), "rb").read(10))
attempt("read_own_environ", lambda: open("/proc/self/environ").read())
attempt("list_root", lambda: os.listdir("/"))
attempt("list_proc_for_other_runs", lambda: os.listdir("/proc"))
attempt("list_tmp", lambda: os.listdir("/tmp"))
attempt("write_a_file", lambda: open({str(tmp_path / "w.txt")!r}, "w").write("x"))
attempt("create_exclusive", lambda: os.open({str(tmp_path / "x.txt")!r}, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
attempt("append", lambda: open({str(secret)!r}, "a").write("x"))
attempt("mkdir", lambda: os.mkdir({str(tmp_path / "d")!r}))
attempt("unlink", lambda: os.unlink({str(secret)!r}))
attempt("rename", lambda: os.rename({str(secret)!r}, {str(tmp_path / "moved")!r}))
attempt("symlink", lambda: os.symlink("/etc/passwd", {str(tmp_path / "l")!r}))
attempt("chmod", lambda: os.chmod({str(secret)!r}, 0o777))
attempt("truncate", lambda: os.truncate({str(secret)!r}, 0))
attempt("tempfile", lambda: __import__("tempfile").TemporaryFile())
attempt("cwd_listing", lambda: os.listdir("."))
""",
    )
    assert_all_blocked(
        results,
        [
            "read_a_file",
            "read_passwd",
            "read_proc_environ_of_the_executor",
            "read_proc_mem_of_the_executor",
            "read_own_environ",
            "list_root",
            "list_proc_for_other_runs",
            "list_tmp",
            "write_a_file",
            "create_exclusive",
            "append",
            "mkdir",
            "unlink",
            "rename",
            "symlink",
            "chmod",
            "truncate",
            "tempfile",
            "cwd_listing",
        ],
    )
    # nothing changed on disk
    assert secret.read_text() == SENTINEL
    assert sorted(p.name for p in tmp_path.iterdir()) == ["secret.txt"]


def test_no_network_of_any_kind():
    # raw system calls: the module `socket` cannot even be imported once the
    # filesystem is gone, and that must not be the only thing in the way
    results = attempts(
        """
attempt("tcp", lambda: raw(41, 2, 1, 0))
attempt("udp", lambda: raw(41, 2, 2, 0))
attempt("ipv6", lambda: raw(41, 10, 1, 0))
attempt("unix", lambda: raw(41, 1, 1, 0))
attempt("netlink", lambda: raw(41, 16, 3, 0))
attempt("raw_ip", lambda: raw(41, 2, 3, 1))
attempt("packet", lambda: raw(41, 17, 3, 0))
attempt("socketpair", lambda: raw(53, 1, 1, 0, 0))
attempt("connect", lambda: raw(42, 3, 0, 16))
attempt("bind", lambda: raw(49, 3, 0, 16))
attempt("listen", lambda: raw(50, 3, 1))
attempt("accept", lambda: raw(43, 3, 0, 0))
attempt("accept4", lambda: raw(288, 3, 0, 0, 0))
attempt("import_socket", lambda: __import__("socket"))
attempt("import_urllib", lambda: __import__("urllib.request"))
attempt("import_ssl", lambda: __import__("ssl"))
""",
    )
    assert_denied_by_seccomp(
        results,
        [
            "tcp",
            "udp",
            "ipv6",
            "unix",
            "netlink",
            "raw_ip",
            "packet",
            "socketpair",
            "connect",
            "bind",
            "listen",
            "accept",
            "accept4",
        ],
    )
    assert_all_blocked(results, ["import_socket", "import_urllib", "import_ssl"])


def test_no_new_processes_no_signals_no_ptrace():
    results = attempts(
        """
attempt("fork", lambda: os.fork())
attempt("execv", lambda: os.execv("/bin/sh", ["sh"]))
def system():
    if os.system("true") == 0:  # 127 << 8: the shell could not even start
        return "the shell ran"
    raise PermissionError(1, "the shell did not start")
attempt("system", system)
attempt("posix_spawn", lambda: os.posix_spawn("/bin/sh", ["sh"], {}))
attempt("kill_the_executor", lambda: os.kill(os.getppid(), 0))
attempt("kill_own_group", lambda: os.killpg(os.getpgid(0), 0))
attempt("fork_raw", lambda: raw(57))
attempt("vfork_raw", lambda: raw(58))
attempt("clone_raw", lambda: raw(56, 0x00010000, 0, 0, 0, 0))
attempt("clone3_raw", lambda: raw(435, 0, 0))
attempt("execve_raw", lambda: raw(59, 0, 0, 0))
attempt("execveat_raw", lambda: raw(322, 0, 0, 0, 0, 0))
attempt("kill_raw", lambda: raw(62, os.getppid(), 0))
attempt("tgkill_raw", lambda: raw(234, os.getppid(), os.getppid(), 0))
attempt("ptrace_the_executor", lambda: raw(101, 16, os.getppid(), 0, 0))
attempt("process_vm_readv", lambda: raw(310, os.getppid(), 0, 0, 0, 0, 0))
attempt("pidfd_open", lambda: raw(434, os.getppid(), 0))
attempt("import_subprocess", lambda: __import__("subprocess"))
attempt("import_threading_then_start", lambda: __import__("threading").Thread(target=lambda: None).start())
""",
    )
    assert_denied_by_seccomp(
        results,
        [
            "fork",
            "execv",
            "system",
            "posix_spawn",
            "kill_the_executor",
            "kill_own_group",
            "fork_raw",
            "vfork_raw",
            "clone_raw",
            "clone3_raw",
            "execve_raw",
            "execveat_raw",
            "kill_raw",
            "tgkill_raw",
            "ptrace_the_executor",
            "process_vm_readv",
            "pidfd_open",
        ],
    )
    assert_all_blocked(results, ["import_subprocess", "import_threading_then_start"])


def test_no_privileges_mounts_namespaces_or_kernel_features():
    results = attempts(
        """
attempt("setuid_root", lambda: os.setuid(0))
attempt("setgid_root", lambda: os.setgid(0))
attempt("setgroups", lambda: os.setgroups([0]))
attempt("chroot", lambda: os.chroot("/"))
attempt("setresuid_raw", lambda: raw(117, 0, 0, 0))
attempt("mount", lambda: raw(165, 0, 0, 0, 0, 0))
attempt("umount2", lambda: raw(166, 0, 0))
attempt("pivot_root", lambda: raw(155, 0, 0))
attempt("unshare_net", lambda: raw(272, 0x40000000))
attempt("unshare_user", lambda: raw(272, 0x10000000))
attempt("setns", lambda: raw(308, 0, 0))
attempt("bpf", lambda: raw(321, 0, 0, 0))
attempt("perf_event_open", lambda: raw(298, 0, 0, 0, 0, 0))
attempt("io_uring_setup", lambda: raw(425, 1, 0))
attempt("userfaultfd", lambda: raw(323, 0))
attempt("keyctl", lambda: raw(250, 0))
attempt("add_key", lambda: raw(248, 0, 0, 0, 0, 0))
attempt("memfd_create", lambda: raw(319, 0, 0))
attempt("openat2", lambda: raw(437, 0, 0, 0, 0))
attempt("open_by_handle_at", lambda: raw(304, 0, 0, 0))
attempt("personality", lambda: raw(135, 0xfffffffe))
attempt("init_module", lambda: raw(175, 0, 0, 0))
attempt("reboot", lambda: raw(169, 0, 0, 0, 0))
attempt("fchmod", lambda: raw(91, 1, 0o777))
attempt("ftruncate", lambda: raw(77, 1, 0))
""",
    )
    assert_denied_by_seccomp(
        results,
        [
            "setuid_root",
            "setgid_root",
            "setgroups",
            "chroot",
            "setresuid_raw",
            "mount",
            "umount2",
            "pivot_root",
            "unshare_net",
            "unshare_user",
            "setns",
            "bpf",
            "perf_event_open",
            "io_uring_setup",
            "userfaultfd",
            "keyctl",
            "add_key",
            "memfd_create",
            "openat2",
            "open_by_handle_at",
            "personality",
            "init_module",
            "reboot",
            "fchmod",
            "ftruncate",
        ],
    )


def test_no_file_descriptor_leaks_in(tmp_path):
    # a descriptor the executor happens to have open and inheritable
    leaked = tmp_path / "leaked.txt"
    leaked.write_text(SENTINEL)
    fd = os.open(leaked, os.O_RDONLY)
    os.set_inheritable(fd, True)
    try:
        outcome = run(
            "import os\n"
            "open_fds = []\n"
            "for fd in range(3, 256):\n"
            "    try:\n"
            "        os.fstat(fd)\n"
            "        open_fds.append(fd)\n"
            "    except OSError:\n"
            "        pass\n"
            "log('open:' + str(open_fds))\n",
            unvalidated=True,
        )
    finally:
        os.close(fd)
    assert outcome.log == ["open:[]"]


def test_the_executor_cannot_be_reached_through_another_run():
    # two runs at once: each child sees only the data it was sent, and neither
    # can find the other (no /proc, no signals, no shared files)
    import asyncio

    from sandbox import broker

    async def both():
        code = "import os\nlog(str(sorted(get_data_keys())))" if False else ""
        mine = (
            "log('mine:' + repr(response))\n"
            "import os\n"
            "try:\n"
            "    log('others:' + str([p for p in os.listdir('/proc') if p.isdigit()]))\n"
            "except OSError as e:\n"
            "    log('others:blocked')\n"
        )
        return await asyncio.gather(
            broker.run_code(
                "response = 'RUN-A'\n" + mine, {}, {}, _unvalidated_for_tests=True
            ),
            broker.run_code(
                "response = 'RUN-B'\n" + mine, {}, {}, _unvalidated_for_tests=True
            ),
        )

    a, b = asyncio.run(both())
    assert a.log == ["mine:'RUN-A'", "others:blocked"]
    assert b.log == ["mine:'RUN-B'", "others:blocked"]


def test_cpu_exhaustion_is_stopped():
    outcome = run(
        "while True:\n    pass\n",
        unvalidated=True,
        cpu_seconds=1,
        timeout_seconds=15,
    )
    assert outcome.error is not None
    assert outcome.error["kind"] in ("cpu_limit", "timeout", "killed")


def test_wall_clock_is_enforced_for_a_code_that_waits():
    import time

    started = time.monotonic()
    outcome = run(
        "import time\ntime.sleep(60)\n",
        unvalidated=True,
        timeout_seconds=2,
    )
    assert outcome.error["kind"] == "timeout"
    assert time.monotonic() - started < 10


@pytest.mark.parametrize(
    "allocation",
    [
        "x = 'a' * (1 << 31)",
        "x = bytearray(1 << 31)",
        "x = [0] * (1 << 29)",
        "x = []\nwhile True:\n    x.append('a' * 1000000)",
    ],
)
def test_memory_exhaustion_is_stopped(allocation):
    outcome = run(allocation, unvalidated=True, memory_mb=128, timeout_seconds=20)
    assert outcome.error is not None
    assert outcome.error["kind"] in ("memory", "killed", "cpu_limit", "error")


def test_a_flood_of_log_lines_is_capped():
    outcome = run(
        "for i in range(2000000):\n    log('x' * 1000)\n",
        unvalidated=True,
        max_log_bytes=10_000,
        cpu_seconds=20,
        timeout_seconds=30,
    )
    assert sum(len(line) + 1 for line in outcome.log) <= 10_000


def test_the_child_cannot_write_to_the_executors_pipe_in_other_ways():
    # it can only talk the protocol; anything else ends the run
    outcome = run(
        "import os\nos.write(1, b'this is not json\\n')\n",
        unvalidated=True,
    )
    assert outcome.error is not None and outcome.error["kind"] == "killed"
