import datetime
from typing import Dict, List, Optional

from beanie import PydanticObjectId

from pydantic import BaseModel, EmailStr, Field

from common.enums.plan import Plans

UserIdentifier = str


class UserPatchRequest(BaseModel):
    """
    Model for patching a user's information.
    """

    first_name: Optional[str]
    last_name: Optional[str]


class UserResponseDto(BaseModel):
    """
    Model for returning information about a user.
    """

    id: PydanticObjectId
    first_name: Optional[str]
    last_name: Optional[str]
    email: str
    roles: List[str] = ["FORM_RESPONDER"]


class UserLoginWithOTP(BaseModel):
    """
    Model for logging in a user with an OTP code.
    """

    email: EmailStr
    otp_code: str


class UserConnectedServices(BaseModel):
    """
    Model for storing information about a user's connected services.
    """

    provider: str
    status: str
    credentials: Dict[str, str]


class User(BaseModel):
    """
    Model for storing information about a user.
    """

    id: str
    sub: UserIdentifier
    plan: Optional[Plans] = Plans.FREE
    roles: Optional[List[str]] = []

    def is_admin(self):
        """
        Returns True if the user has the 'ADMIN' role, False otherwise.
        """
        return "ADMIN" in self.roles

    def is_not_admin(self):
        """
        Returns True if the user does not have the 'ADMIN' role, False otherwise.
        """
        return not self.is_admin()


class AuthenticationStatus(BaseModel):
    """
    Model for storing the authentication status of a user.
    """

    user: User = Field()


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Optional[str]
    expires_in: Optional[int]


class UserInfo(BaseModel):
    email: str
    first_name: Optional[str]
    last_name: Optional[str]


class OAuthState(BaseModel):
    client_referer_uri: Optional[str]
    email: Optional[str]


class Credential(BaseModel):
    updated_at: Optional[datetime.datetime]
    email: str
    access_token: str
    refresh_token: Optional[str]
    access_token_expires: Optional[int]
    refresh_token_expires: Optional[int]
