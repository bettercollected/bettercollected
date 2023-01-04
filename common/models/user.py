from typing import Dict, Optional, List

from beanie import PydanticObjectId
from pydantic import BaseModel, EmailStr, Field

UserIdentifier = str


class UserPatchRequest(BaseModel):
    first_name: Optional[str]
    last_name: Optional[str]
    username: Optional[str]


class UserResponseDto(BaseModel):
    id: PydanticObjectId
    first_name: Optional[str]
    last_name: Optional[str]
    username: Optional[str]
    email: str
    roles: List[str] = ["FORM_RESPONDER"]
    services: Optional[List[str]]


class UserLoginWithOTP(BaseModel):
    email: EmailStr
    otp_code: str


class UserConnectedServices(BaseModel):
    provider: str
    status: str
    credentials: Dict[str, str]


class User(BaseModel):
    id: str
    sub: UserIdentifier
    username: Optional[str] = Field()
    roles: Optional[List[str]] = []
    services: Optional[List[str]] = []

    def is_admin(self):
        return "ADMIN" in self.roles

    def is_not_admin(self):
        return not self.is_admin()


class AuthenticationStatus(BaseModel):
    user: User = Field()
