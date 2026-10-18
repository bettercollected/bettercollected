"""Task contracts and the registry's invariants (no database)."""

from __future__ import annotations

import enum
import re
from typing import Optional

import pytest

from backend.admin.services import audit
from backend.admin.tasks import catalog
from backend.admin.tasks import impl as impl_package
from backend.admin.tasks.catalog import selftest, selftest_slow
from backend.admin.tasks.registry import (
    Registry,
    RegistryError,
    check_meta,
    check_params,
    check_result,
)
from backend.admin.tasks.spec import (
    DENY_FIELD_NAME,
    Id,
    Params,
    Refusal,
    Result,
    TaskError,
    TaskMeta,
)


class E(str, enum.Enum):
    ok = "ok"


class Mode(str, enum.Enum):
    a = "a"


class P(Params):
    n: int = 1


class R(Result):
    n: int


def meta(**kw):
    base = dict(name="demo", version=1, params=P, result=R, events=E, mutating=False)
    base.update(kw)
    return TaskMeta(**base)


class Impl:
    async def precheck(self, ctx, params):
        return None

    async def run(self, ctx, params):
        return R(n=1)


def test_the_deny_list_is_the_audit_mask_list():
    assert DENY_FIELD_NAME.pattern == audit._DENY.pattern


@pytest.mark.parametrize(
    "name",
    [
        "secret", "api_key", "token", "password", "passwd", "otp", "code", "hash",
        "auth_header", "cookie", "seed", "private_note", "database_url", "dsn",
        "credential", "bearer", "jwt", "signature", "salt", "recovery_code",
        "SecretValue", "keyset_id",
    ],
)
def test_params_with_secret_looking_names_are_rejected(name):
    model = type("Bad", (Params,), {"__annotations__": {name: str}})
    with pytest.raises(RegistryError, match="secret"):
        check_params(model)


@pytest.mark.parametrize("name", ["workspace_id", "batch_size", "dry", "limit", "form_id", "passed"])
def test_ordinary_parameter_names_are_fine(name):
    check_params(type("Ok", (Params,), {"__annotations__": {name: int}}))


def test_params_forbid_unknown_fields():
    with pytest.raises(Exception):
        P(n=1, extra=2)
    with pytest.raises(Exception):
        P.model_validate({"n": 1, "surprise": True})


def test_results_may_only_hold_ints_bools_enums_and_ids():
    class Good(Result):
        a: int
        b: bool
        c: Mode
        d: Id
        e: Optional[int] = None
        f: Optional[Id] = None

    check_result(Good)
    for bad in (str, float, list[int], dict, bytes):
        model = type("Bad", (Result,), {"__annotations__": {"x": bad}})
        with pytest.raises(RegistryError, match="free text"):
            check_result(model)


def test_a_plain_string_result_field_is_free_text():
    class Bad(Result):
        message: str

    with pytest.raises(RegistryError):
        check_result(Bad)


def test_meta_rules():
    check_meta(meta())
    with pytest.raises(RegistryError):
        check_meta(meta(name="Bad Name"))
    with pytest.raises(RegistryError):
        check_meta(meta(version=0))
    with pytest.raises(RegistryError):
        check_meta(meta(requires_prior_dry_run=True))  # not mutating

    class Reserved(str, enum.Enum):
        truncated = "truncated"

    with pytest.raises(RegistryError, match="reserved"):
        check_meta(meta(events=Reserved))
    with pytest.raises(RegistryError):
        check_meta(meta(resources=("task:other",)))
    check_meta(meta(name="responses.check_undecryptable"))


def test_names_are_unique_and_implementations_must_be_async():
    registry = Registry()
    registry.register(meta(), Impl())
    with pytest.raises(RegistryError, match="already"):
        registry.register(meta(), Impl())

    class Sync:
        def precheck(self, ctx, params):
            return None

        async def run(self, ctx, params):
            return R(n=1)

    with pytest.raises(RegistryError, match="async"):
        Registry().register(meta(name="other"), Sync())


def test_the_decorator_registers_an_instance():
    registry = Registry()

    @registry.task(meta(name="decorated"))
    class Decorated(Impl):
        pass

    assert registry.get("decorated").meta.name == "decorated"
    assert registry.names() == ["decorated"]
    assert "decorated" in registry and len(registry) == 1


def test_refusal_and_error_codes_are_short_tokens_not_prose():
    assert Refusal("keyset_missing").code == "keyset_missing"
    assert TaskError("planted_failure").code == "planted_failure"
    for bad in ("", "Has Spaces", "x" * 80, "user@example.org"):
        with pytest.raises(ValueError):
            Refusal(bad)
        with pytest.raises(ValueError):
            TaskError(bad)


def test_the_selftest_tasks_meet_every_rule():
    for m in (selftest.META, selftest_slow.META, selftest_slow.GUARDED_META):
        check_meta(m)
        assert m.internal


REAL = ["responses.backfill_workspaces", "responses.check_undecryptable"]


def test_selftest_tasks_are_registered_only_when_flagged():
    assert [m.name for m in catalog.all_meta({})] == [
        "responses.check_undecryptable",
        "responses.backfill_workspaces",
    ]
    assert [m.name for m in catalog.all_meta({"ADMIN_TASKS_SELFTEST": "0"})] == [
        "responses.check_undecryptable",
        "responses.backfill_workspaces",
    ]
    assert impl_package.build_registry({}).names() == REAL
    flagged = {"ADMIN_TASKS_SELFTEST": "1"}
    assert [m.name for m in catalog.all_meta(flagged)] == [
        "responses.check_undecryptable",
        "responses.backfill_workspaces",
        "selftest",
        "selftest_slow",
        "selftest_guarded",
    ]
    assert impl_package.build_registry(flagged).names() == sorted(
        REAL + ["selftest", "selftest_guarded", "selftest_slow"]
    )


def test_selftest_is_read_only_and_the_slow_one_mutates():
    assert selftest.META.mutating is False
    assert selftest_slow.META.mutating is True
    assert re.match(r"^[a-z_]+$", selftest_slow.META.name)
