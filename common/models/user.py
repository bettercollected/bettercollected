from typing import Dict, Optional, List

from beanie import PydanticObjectId
from pydantic import BaseModel, EmailStr, Field

from common.enums.form_provider import FormProvider

UserIdentifier = str


class UserPatchRequest(BaseModel):
    """
    Model for patching a user's information.
    """

    first_name: Optional[str]
    last_name: Optional[str]
    username: Optional[str]


class UserResponseDto(BaseModel):
    """
    Model for returning information about a user.
    """

    id: PydanticObjectId
    first_name: Optional[str]
    last_name: Optional[str]
    username: Optional[str]
    email: str
    roles: List[str] = ["FORM_RESPONDER"]
    services: Optional[List[str]]


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
    username: Optional[str] = Field()
    roles: Optional[List[str]] = []
    services: Optional[List[str]] = []

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
    token_type: str
    expires_in: int


class UserInfo(Token):
    email: str
    provider: str


class OAuthState(BaseModel):
    # Redirect uri for saving user after successful typeform authentication
    auth_server_redirect_uri: Optional[str]
    backend_auth_redirect_uri: Optional[str]
    client_referer_uri: Optional[str]
