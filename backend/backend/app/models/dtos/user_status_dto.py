from typing import Optional, List

from fastapi_camelcase import CamelModel
from pydantic import EmailStr

from common.enums.plan import Plans
from common.enums.roles import Roles


class UserStatusDto(CamelModel):
    id: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    profile_image: Optional[str] = None
    email: EmailStr
    roles: List[str] = [Roles.FORM_RESPONDER]
    plan: Optional[Plans] = Plans.FREE
    stripe_customer_id: Optional[str] = None
    stripe_payment_id: Optional[str] = None
    tags: Optional[List[str]] = None
