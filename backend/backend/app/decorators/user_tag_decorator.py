from functools import wraps

from backend.app.container import container
from backend.app.models.enum.user_tag_enum import UserTagType
from common.models.user import User


def user_tag(tag: UserTagType):
    def decorator(func):
        @wraps(func)
        async def wrapper(self, user_tags_service=container.user_tags_service(), *args, **kwargs):
            user: User = kwargs.get("user")
            fun_response = await func(self, *args, **kwargs)
            await user_tags_service.add_user_tag(user_id=user.id, tag=tag)
            return fun_response

        return wrapper

    return decorator
