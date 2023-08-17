from functools import wraps

from backend.app.container import container
from backend.app.models.enum.user_tag_enum import UserTagType
from backend.app.models.workspace import WorkspaceResponseDto
from backend.app.services.workspace_service import WorkspaceService
from common.models.user import User


def user_tag(tag: UserTagType):
    def decorator(func):
        @wraps(func)
        async def wrapper(
            self, user_tags_service=container.user_tags_service(), *args, **kwargs
        ):
            user: User = kwargs.get("user")
            func_response = await func(self, *args, **kwargs)
            await user_tags_service.add_user_tag(user_id=user.id, tag=tag)
            return func_response

        return wrapper

    return decorator


def user_tag_from_workspace(tag: UserTagType):
    def decorator(func):
        @wraps(func)
        async def wrapper(
            self,
            user_tags_service=container.user_tags_service(),
            workspace_service: WorkspaceService = container.workspace_service(),
            *args,
            **kwargs
        ):
            workspace_id: User = kwargs.get("workspace_id")
            func_response = await func(self, *args, **kwargs)

            workspace: WorkspaceResponseDto = (
                await workspace_service.get_workspace_by_id(workspace_id=workspace_id)
            )
            await user_tags_service.add_user_tag(user_id=workspace.owner_id, tag=tag)
            return func_response

        return wrapper

    return decorator
