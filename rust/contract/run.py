#!/usr/bin/env python3
"""The contract harness: the same requests to the Python backend and to the Rust edge.

    uv run --project backend python rust/contract/run.py [options]

What it does, on one throw-away database:

1. creates a fresh database (its name must contain "test") from ``DATABASE_URL``,
2. migrates it and seeds workspaces, members and tokens through the Python
   backend's own code (``seed.py``),
3. for every set of environment variables the corpus asks for, starts the Python
   backend and the Rust edge (``BC_RUST_ROUTES`` = the groups of the corpus files
   run, ``BC_PYTHON_UPSTREAM`` = the Python backend),
4. sends every case to both, and compares status, headers and the JSON after
   parse (``compare.py``); a write case also compares the database rows the two
   left behind (``dbdiff.py``),
5. with ``--passthrough`` also runs the whole corpus against an edge that serves no
   group at all: the pass-through must change nothing,
6. prints a short report and exits non-zero on any difference.

``DATABASE_URL`` supplies the server and the credentials only; the database used is
``--database-name`` (default ``bc_contract_test``), created fresh and dropped at the end.

Needs the environment of the backend's tests (``.github/workflows/ci.yml``,
``backend-tests``): AUTH_AES_HEX_KEY, MASTER_ENCRYPTION_KEYSET, DATABASE_URL, ...
AUTH_JWT_SECRET is replaced by a ring of two generated secrets for the run, so
the tokens signed with the previous key can be tested; nothing real is used.
"""

from __future__ import annotations

import argparse
import asyncio
import http.client
import json
import os
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import corpus
import dbdiff
from compare import Answer, compare

HERE = Path(__file__).resolve().parent
RUST_DIR = HERE.parent
REPO = RUST_DIR.parent
HOST_HEADER = "contract.test"
REQUEST_TIMEOUT = 20


# ------------------------------------------------------------------ helpers

def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def send(base: str, method: str, path: str, headers: dict, body) -> Answer:
    parts = urlsplit(base)
    try:
        conn = http.client.HTTPConnection(parts.hostname, parts.port, timeout=REQUEST_TIMEOUT)
        outgoing = {"Host": HOST_HEADER, **headers}
        conn.request(method, path, body=body, headers=outgoing)
        response = conn.getresponse()
        data = response.read()
        heads: dict = {}
        for name, value in response.getheaders():
            heads.setdefault(name.lower(), []).append(value)
        conn.close()
        return Answer(response.status, heads, data)
    except (OSError, http.client.HTTPException) as error:
        return Answer(0, {}, b"", error=f"{type(error).__name__}")


def database_parts(url: str):
    """(url of the maintenance database, name of the test database)."""
    parts = urlsplit(url)
    name = parts.path.lstrip("/")
    if "test" not in name:
        sys.exit(f"refusing to use a database whose name has no 'test' in it: {name!r}")
    admin = urlunsplit(parts._replace(path="/postgres"))
    return admin, name


def plain_dsn(url: str) -> str:
    """asyncpg does not know SQLAlchemy's driver suffix."""
    return url.replace("postgresql+asyncpg://", "postgresql://", 1)


async def recreate_database(url: str) -> None:
    import asyncpg

    admin, name = database_parts(url)
    conn = await asyncpg.connect(plain_dsn(admin))
    try:
        await conn.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
        await conn.execute(f'CREATE DATABASE "{name}"')
    finally:
        await conn.close()


async def drop_database(url: str) -> None:
    import asyncpg

    admin, name = database_parts(url)
    conn = await asyncpg.connect(plain_dsn(admin))
    try:
        await conn.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
    finally:
        await conn.close()


class Server:
    def __init__(self, name: str, argv: list, env: dict, cwd: Path, log: Path):
        self.name = name
        self.log = log
        self.handle = log.open("wb")
        self.process = subprocess.Popen(
            argv, env=env, cwd=cwd, stdout=self.handle, stderr=subprocess.STDOUT, start_new_session=True
        )

    def alive(self) -> bool:
        return self.process.poll() is None

    def stop(self) -> None:
        if self.alive():
            try:
                os.killpg(self.process.pid, signal.SIGTERM)  # only the group this harness started
                self.process.wait(timeout=15)
            except (subprocess.TimeoutExpired, ProcessLookupError):
                try:
                    os.killpg(self.process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
        self.handle.close()

    def tail(self, lines: int = 25) -> str:
        try:
            return "\n".join(self.log.read_text(errors="replace").splitlines()[-lines:])
        except OSError:
            return ""


def wait_ready(server: Server, base: str, path: str, timeout: float) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not server.alive():
            sys.exit(f"{server.name} exited during start:\n{server.tail()}")
        if send(base, "GET", path, {}, None).status:
            return
        time.sleep(0.3)
    server.stop()
    sys.exit(f"{server.name} did not answer within {timeout:.0f}s:\n{server.tail()}")


# --------------------------------------------------------------------- runs

def run_seed(args: list, env: dict) -> None:
    command = ["uv", "run", "--frozen", "--project", str(REPO / "backend"), "python", str(HERE / "seed.py"), *args]
    done = subprocess.run(command, env=env, cwd=REPO / "backend", capture_output=True, text=True)
    if done.returncode:
        sys.exit(f"seed.py {args[0]} failed:\n{done.stdout[-1500:]}\n{done.stderr[-1500:]}")


def rust_binary(arg: str | None) -> Path:
    if arg:
        return Path(arg)
    target = os.environ.get("CARGO_TARGET_DIR") or str(RUST_DIR / "target")
    return Path(target) / "debug" / "bc-api"


class Pair:
    """A Python backend and a Rust edge in front of it, for one environment."""

    def __init__(self, env_extra: dict, rust_routes: list, base_env: dict, rust_bin: Path, logdir: Path, label: str):
        self.py_port, self.rs_port = free_port(), free_port()
        env = {**base_env, **env_extra}
        self.python = Server(
            f"python[{label}]",
            ["uv", "run", "--frozen", "python", "-m", "uvicorn", "backend.app:get_application", "--factory",
             "--host", "127.0.0.1", "--port", str(self.py_port), "--no-access-log"],
            env, REPO / "backend", logdir / f"python-{label}.log",
        )
        self.rust = None
        self.py_url = f"http://127.0.0.1:{self.py_port}"
        self.rs_url = f"http://127.0.0.1:{self.rs_port}"
        self._rust_args = (env, rust_routes, rust_bin, logdir, label)

    def start(self) -> None:
        wait_ready(self.python, self.py_url, "/api/v1/__ready__", 120)
        env, routes, rust_bin, logdir, label = self._rust_args
        renv = dict(env)
        renv.update(
            BC_PYTHON_UPSTREAM=self.py_url,
            BC_RUST_ROUTES=",".join(routes),
            BC_SERVED_BY_HEADER="true",
            BC_API_BIND=f"127.0.0.1:{self.rs_port}",
            RUST_LOG="info",
        )
        self.rust = Server(f"rust[{label}]", [str(rust_bin)], renv, REPO, logdir / f"rust-{label}.log")
        wait_ready(self.rust, self.rs_url, "/health", 30)

    def stop(self) -> None:
        for server in (self.rust, self.python):
            if server:
                server.stop()


class Tally:
    def __init__(self):
        self.cases = 0
        self.identical = 0
        self.skipped = 0
        self.differences: list = []
        self.served = {"rust": 0, "python": 0, "unknown": 0}
        self.db_cases = 0

    def line(self, label: str) -> str:
        return (
            f"{label}: {self.cases} cases, {self.identical} identical, {len(self.differences)} differences; "
            f"served by rust {self.served['rust']}, python {self.served['python']}"
            + (f"; {self.db_cases} with a row diff" if self.db_cases else "")
        )


async def run_db_case(dsn: str, case: corpus.Case, pair: Pair) -> tuple:
    import asyncpg

    tables = case.db["tables"]
    ignored = case.db.get("ignore_columns")
    conn = await asyncpg.connect(dsn)
    try:
        before = await dbdiff.snapshot(conn, tables)
        py = await asyncio.to_thread(send, pair.py_url, case.method, case.path, case.headers, case.body)
        after_py = await dbdiff.snapshot(conn, tables)
        await dbdiff.restore(conn, before)
        rs = await asyncio.to_thread(send, pair.rs_url, case.method, case.path, case.headers, case.body)
        after_rs = await dbdiff.snapshot(conn, tables)
        await dbdiff.restore(conn, before)
        problems = dbdiff.compare_deltas(dbdiff.diff(before, after_py), dbdiff.diff(before, after_rs), ignored)
        problems += [f"python wrote a bad checksum: {r}" for r in dbdiff.bad_checksums(after_py)]
        problems += [f"rust wrote a bad checksum: {r}" for r in dbdiff.bad_checksums(after_rs)]
        return py, rs, problems
    finally:
        await conn.close()


def run_cases(files: list, pair: Pair, dsn: str, tally: Tally, rust_enabled: bool) -> None:
    for cfile in files:
        for case in cfile.cases:
            tally.cases += 1
            problems: list = []
            if case.db:
                tally.db_cases += 1
                py, rs, problems = asyncio.run(run_db_case(dsn, case, pair))
            else:
                py = send(pair.py_url, case.method, case.path, case.headers, case.body)
                rs = send(pair.rs_url, case.method, case.path, case.headers, case.body)
            verdict = compare(py, rs)
            served = rs.served_by or "unknown"
            tally.served[served if served in tally.served else "unknown"] += 1
            expected = case.served_by if rust_enabled else "python"
            if expected and served != expected:
                verdict.differences.append(f"served by {served}, expected {expected}")
            verdict.differences.extend(problems)
            if verdict.equal:
                tally.identical += 1
            else:
                tally.differences.append((cfile.group, case, verdict.differences))


def selfcheck_db_hook(dsn: str) -> str:
    """Proves the snapshot, diff and restore hook against the real database
    before any case relies on it: change a row by hand, see it in the diff and in the
    checksum check, put it back, see that nothing differs."""
    import asyncpg

    async def go() -> str:
        conn = await asyncpg.connect(dsn)
        try:
            before = await dbdiff.snapshot(conn, ["workspaces", "workspace_users"])
            if not before["workspaces"]:
                return "no workspaces to check with"
            bad = dbdiff.bad_checksums(before)
            if bad:
                return f"stored checksums that do not match their doc: {bad[:3]}"
            row_id = next(iter(before["workspaces"]))
            await conn.execute(
                "UPDATE app.workspaces SET doc = jsonb_set(doc, '{title}', '\"changed by the self-check\"') WHERE id = $1",
                row_id,
            )
            changed = await dbdiff.snapshot(conn, ["workspaces", "workspace_users"])
            delta = dbdiff.diff(before, changed)
            if row_id not in delta.get("workspaces", {}).get("changed", {}):
                return "the diff did not see a changed row"
            # a writer that changes doc and not the checksum (raw SQL, as here) must be caught
            if f"workspaces/{row_id}" not in dbdiff.bad_checksums(changed):
                return "the checksum check did not catch a doc changed without its checksum"
            await dbdiff.restore(conn, before)
            after = await dbdiff.snapshot(conn, ["workspaces", "workspace_users"])
            leftover = dbdiff.normalise(dbdiff.diff(before, after))
            changed_rows = {t: p["changed"] for t, p in leftover.items() if p["changed"] or p["added"] or p["removed"]}
            if changed_rows:
                return f"restore left a difference: {json.dumps(changed_rows)[:200]}"
            return ""
        finally:
            await conn.close()

    return asyncio.run(go())


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cases", default=str(HERE / "cases"), help="directory of corpus files")
    ap.add_argument("--group", action="append", help="run only this route group (repeatable)")
    ap.add_argument("--rust-bin", help="the bc-api binary (default: debug build in the cargo target directory)")
    ap.add_argument("--passthrough", action="store_true", help="also run every environment with no group switched on: the pass-through must change nothing")
    ap.add_argument("--database-name", default="bc_contract_test",
                    help="the database to create, fill and drop (must contain 'test'); DATABASE_URL only gives the server and the credentials, "
                         "the database it names is never touched")
    ap.add_argument("--keep-db", action="store_true", help="do not drop the database at the end")
    ap.add_argument("--report", help="write the full result as JSON to this file")
    ap.add_argument("--logs", help="keep the server logs in this directory (default: a temporary one, removed)")
    args = ap.parse_args()

    server_url = os.environ.get("DATABASE_URL")
    if not server_url:
        sys.exit("DATABASE_URL is not set")
    url = urlunsplit(urlsplit(server_url)._replace(path="/" + args.database_name))
    database_parts(url)  # refuses a name without "test"
    rust_bin = rust_binary(args.rust_bin)
    if not rust_bin.exists():
        sys.exit(f"{rust_bin} does not exist: build it with `cargo build -p bc-api` in rust/")

    # a ring of two throw-away secrets for this run (the previous key is tested)
    base_env = dict(os.environ)
    base_env["AUTH_JWT_SECRET"] = f"{secrets.token_hex(32)},{secrets.token_hex(32)}"
    # the backend refuses to start without a respondent identity key: a throw-away one
    base_env.setdefault("RESPONDENT_IDENTITY_KEY", secrets.token_hex(32))
    base_env["DATABASE_URL"] = url
    for name in list(base_env):
        if name.startswith("BC_"):
            del base_env[name]
    os.environ["AUTH_JWT_SECRET"] = base_env["AUTH_JWT_SECRET"]

    logdir = Path(args.logs) if args.logs else Path(tempfile.mkdtemp(prefix="bc-contract-"))
    logdir.mkdir(parents=True, exist_ok=True)
    fixture_path = logdir / "fixture.json"

    asyncio.run(recreate_database(url))
    pairs: list = []
    exit_code = 1
    try:
        run_seed(["migrate"], base_env)
        run_seed(["seed", str(fixture_path)], base_env)
        run_seed(["extend", str(fixture_path)], base_env)
        fixture = json.loads(fixture_path.read_text())
        fixture["workspaces"]["main_upper"] = fixture["workspaces"]["main"].upper()

        files = corpus.load_dir(Path(args.cases), fixture, set(args.group) if args.group else None)
        if not files:
            sys.exit("no corpus files selected")
        problem = selfcheck_db_hook(plain_dsn(url))
        if problem:
            sys.exit(f"db hook self-check failed: {problem}")
        print("db hook self-check: ok")

        by_env: dict = {}
        for cfile in files:
            by_env.setdefault(json.dumps(cfile.env, sort_keys=True), []).append(cfile)

        tallies = []
        for n, (env_key, group_files) in enumerate(by_env.items()):
            env_extra = json.loads(env_key)
            routes = sorted({f.group for f in group_files})
            modes = [("rust", routes)]
            if args.passthrough:
                modes.append(("passthrough", []))
            for mode, switched_on in modes:
                label = f"{n}-{mode}"
                pair = Pair(env_extra, switched_on, base_env, rust_bin, logdir, label)
                pairs.append(pair)
                pair.start()
                tally = Tally()
                run_cases(group_files, pair, plain_dsn(url), tally, rust_enabled=bool(switched_on))
                pair.stop()
                title = f"{', '.join(Path(f.path).name for f in group_files)} [{mode}]"
                if env_extra:
                    title += f" env={json.dumps(env_extra, sort_keys=True)[:80]}"
                tallies.append((title, tally))

        total_cases = sum(t.cases for _, t in tallies)
        total_diff = sum(len(t.differences) for _, t in tallies)
        for title, tally in tallies:
            print(tally.line(title))
            for group, case, why in tally.differences:
                print(f"DIFF {group} {case.name} {case.method} {case.path[:80]}")
                for w in why:
                    print("     ", w)
        print(f"contract: {total_cases} cases, {total_diff} differences")
        if args.report:
            Path(args.report).write_text(json.dumps({
                "cases": total_cases, "differences": total_diff,
                "runs": [{"title": t, "cases": x.cases, "identical": x.identical, "served": x.served,
                          "differences": [{"group": g, "case": c.name, "why": w} for g, c, w in x.differences]}
                         for t, x in tallies],
            }, indent=1))
        exit_code = 1 if total_diff else 0
    finally:
        for pair in pairs:
            pair.stop()
        if not args.keep_db:
            try:
                asyncio.run(drop_database(url))
            except Exception as error:  # never hide the result behind a cleanup problem
                print(f"could not drop the database: {type(error).__name__}", file=sys.stderr)
        if not args.logs:
            shutil.rmtree(logdir, ignore_errors=True)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
