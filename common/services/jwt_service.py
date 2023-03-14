from typing import TypeVar, Type

import jwt
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class JwtService:

    def __init__(self, jwt_secret: str):
        self.jwt_secret = jwt_secret

    def encode(self, model: BaseModel) -> str:
        return jwt.encode(
            model.dict(exclude_none=True), key=self.jwt_secret
        )

    def decode(self, token: str, model: Type[T]) -> T:
        decoded_data = jwt.decode(
            token,
            key=self.jwt_secret,
            algorithms=["HS256"],
        )
        return model.parse_obj(decoded_data)
