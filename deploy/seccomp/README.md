# Seccomp profile of the document sandbox

`document-sandbox.json` is the syscall filter of the `document-sandbox` service in
`docker-compose.deployment.yml` and `docker-compose.local.yml` (issue #703). That
container opens uploaded PDFs and photos for the form import, with native code
(pdfium, Pillow's decoders), so it assumes that a crafted file can run code in it.
The filter comes on top of the other isolation: `nobody`, no network, read-only
filesystem, no capabilities, `no-new-privileges`, no environment file.

Compose loads it with `security_opt: - seccomp=./deploy/seccomp/document-sandbox.json`,
relative to the compose file's directory, so run compose from a checkout of the
repository (as `deploy.sh` does).

## What it allows

The same semantics as Docker's default profile, with a much shorter list:

- **An allowlist.** Anything not listed fails with `EPERM` (`defaultAction:
  SCMP_ACT_ERRNO`). Nothing is killed, so a syscall that is missing shows up as
  an error and can be found.
- What CPython, pypdf, pdfplumber/pdfminer, pypdfium2 and Pillow need to parse
  and render: files, memory, signals, time, futexes, resource limits.
- The asyncio server on its Unix socket and the fork/exec of each request's
  child (`python -I _child.py`). `socket` and `socketpair` only for `AF_UNIX`.
  `clone` without namespace flags, and `clone3` answers `ENOSYS` as in Docker's
  default profile, so glibc falls back to `clone`.
- The native 64-bit ABI of x86_64 and aarch64 only (no x86/x32 compatibility
  syscalls).

Denied, among others: every network socket (`AF_INET`, `AF_INET6`, netlink,
packet), `ptrace` and `process_vm_*`, `mount`, `unshare`, `setns`, `keyctl`,
`add_key`, `bpf`, `perf_event_open`, `io_uring_*`, `userfaultfd`, `personality`,
module loading, `symlink`/`link`, and the set*id family.

## Changing it

The list came from `strace -f` of the server while it read the synthetic test
documents in every mode (analyze, text, layout, render, PDF and photo). When a
library upgrade or a new mode needs another syscall, the sandbox returns
"could not read" for documents that used to work:

1. Build a throwaway image with strace: `FROM bettercollected/backend:<tag>`,
   `RUN apt-get update && apt-get install -y strace`.
2. Run the server under `strace -f -o /trace/t` with `--cap-add SYS_PTRACE
   --security-opt seccomp=unconfined` (only for this), send it the documents, and
   list the syscall names in the trace.
3. Add what is missing (and harmless) to the allowlist in the JSON, with its
   group in the rule's `comment`.

Then check it for real:

```bash
docker build -f backend/Dockerfile -t bettercollected/backend:sandbox-test .
cd backend && uv run pytest tests/app/pdf_import/test_sandbox_container.py
```

The test starts the container with this profile, reads every mode over the
socket, and checks from inside that network sockets, `ptrace`, `mount`,
`unshare`, `keyctl`, `bpf` and `io_uring` fail with `EPERM` (it is skipped
without docker or the image).
