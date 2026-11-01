"""The ``monkeypatch`` fixture (tests/conftest.py) deletes what it added to an
instance: pytest's own restores the class's bound method as an instance
attribute, which then shadows the class for every later test of the worker
(the cause of a flaky ``patch.object(Service, "method")`` that was ignored)."""

import pytest
from unittest.mock import AsyncMock, patch

from backend.app.container import container


class Service:
    def method(self):
        return "real"

    def other(self):
        return "other"


def test_an_instance_is_left_without_the_attribute(monkeypatch):
    service = Service()
    monkeypatch.setattr(service, "method", lambda: "fake")
    assert service.method() == "fake"
    monkeypatch.undo()
    assert "method" not in vars(service)
    with patch.object(Service, "method", lambda self: "class patch"):
        assert service.method() == "class patch"


def test_an_attribute_the_instance_already_had_is_restored_not_deleted(monkeypatch):
    service = Service()
    service.method = lambda: "own"
    monkeypatch.setattr(service, "method", lambda: "fake")
    monkeypatch.undo()
    assert service.method() == "own"


def test_class_module_and_string_targets_work_as_before(monkeypatch):
    monkeypatch.setattr(Service, "other", lambda self: "patched")
    assert Service().other() == "patched"
    monkeypatch.setattr("tests.app.test_monkeypatch_leaves_instances_clean.Service.method", lambda self: "by name")
    assert Service().method() == "by name"
    monkeypatch.undo()
    assert Service().other() == "other" and Service().method() == "real"


def test_a_container_singleton_is_clean_after_the_fixture_ends(monkeypatch):
    service = container.form_response_service()
    monkeypatch.setattr(service, "workspace_response", AsyncMock(return_value=None))
    monkeypatch.undo()
    assert "workspace_response" not in vars(service)
    monkeypatch.setattr(container.rate_limiter(), "_clock", lambda: 1.0)  # an instance attribute already
    monkeypatch.undo()
    assert container.rate_limiter()._clock() != 1.0
