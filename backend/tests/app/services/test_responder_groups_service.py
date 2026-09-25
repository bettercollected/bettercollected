"""A responder group's regex is validated before it is stored: a pattern that
does not compile would otherwise be evaluated against every responder when the
workspace's private forms are listed."""

from http import HTTPStatus
from unittest.mock import AsyncMock

import pytest
from beanie import PydanticObjectId

from backend.app.exceptions import HTTPException
from backend.app.services.responder_groups_service import (
    ResponderGroupsService,
    validate_group_regex,
)
from common.models.user import User


@pytest.mark.parametrize("regex", [None, "", ".*@corp.com", "^dev@"])
def test_valid_or_empty_regex_is_accepted(regex):
    validate_group_regex(regex)


@pytest.mark.parametrize("regex", ["*@corp.com", "(unclosed", "a{2,1}"])
def test_pattern_that_does_not_compile_is_rejected(regex):
    with pytest.raises(HTTPException) as raised:
        validate_group_regex(regex)
    assert raised.value.status_code == HTTPStatus.BAD_REQUEST


def _service():
    repo = AsyncMock()
    workspace_users = AsyncMock()
    service = ResponderGroupsService(repo, workspace_users, form_service=AsyncMock())
    return service, repo


async def test_create_group_rejects_bad_regex_before_writing():
    service, repo = _service()
    user = User(id=str(PydanticObjectId()), sub="admin@example.com")
    with pytest.raises(HTTPException):
        await service.create_group(
            PydanticObjectId(), "Glob", [], user, None, "", regex="*@corp.com"
        )
    repo.create_group.assert_not_awaited()


async def test_update_group_rejects_bad_regex_before_writing():
    service, repo = _service()
    service.check_user_can_access_group = AsyncMock()
    user = User(id=str(PydanticObjectId()), sub="admin@example.com")
    with pytest.raises(HTTPException):
        await service.update_responder_group(
            PydanticObjectId(), PydanticObjectId(), user, "Glob", [], "*@corp.com", ""
        )
    repo.update_group.assert_not_awaited()
