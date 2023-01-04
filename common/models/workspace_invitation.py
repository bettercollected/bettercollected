from typing import List

from pydantic import BaseModel


class InvitationRequestBody(BaseModel):
    email: str
    roles: List[str] = ["FORM_CREATOR"]


class InvitationRequestWithToken(InvitationRequestBody):
    token: str


class InvitationActionRequest(BaseModel):
    action: bool
