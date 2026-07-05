import datetime
from typing import Dict, List, Optional

from beanie import PydanticObjectId
from pydantic import BaseModel, EmailStr, Field

from common.enums.plan import Plans
from common.enums.roles import Roles

UserIdentifier = str


class UserPatchRequest(BaseModel):
    """
    Model for patching a user's information.
    """

    first_name: Optional[str] = None
    last_name: Optional[str] = None


class UserResponseDto(BaseModel):
    """
    Model for returning information about a user.
    """

    id: PydanticObjectId
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: str
    plan: Optional[Plans] = Plans.FREE
    profile_image: Optional[str] = None
    stripe_customer_id: Optional[str] = None
    roles: List[str] = [Roles.FORM_RESPONDER]


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
    token_type: Optional[str] = None
    expires_in: Optional[int] = None


class UserInfo(BaseModel):
    user_id: Optional[str] = None
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None


class OAuthState(BaseModel):
    client_referer_uri: Optional[str] = None
    email: Optional[str] = None


class Credential(BaseModel):
    updated_at: Optional[datetime.datetime] = None
    email: str
    access_token: str
    refresh_token: Optional[str] = None
    access_token_expires: Optional[int] = None
    refresh_token_expires: Optional[int] = None
