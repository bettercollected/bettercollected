from typing import TypeVar, Type

import jwt
from pydantic import BaseModel

from backend.config import settings

T = TypeVar("T", bound=BaseModel)


class JwtService:

    @staticmethod
    def encode(model: BaseModel) -> str:
        return jwt.encode(
            model.dict(exclude_none=True),
            key=settings.auth_settings.JWT_SECRET)

    @staticmethod
    def decode(token: str, model: Type[T]) -> T:
        decoded_data = jwt.decode(
            token,
            key=settings.auth_settings.JWT_SECRET,
            algorithms=["HS256"],
        )
        return model.parse_obj(decoded_data)
