from typing import Optional, List

from fastapi_camelcase import CamelModel
from pydantic import EmailStr

from common.enums.plan import Plans
from common.enums.roles import Roles


class UserStatusDto(CamelModel):
    id: str
    first_name: Optional[str]
    last_name: Optional[str]
    profile_image: Optional[str]
    email: EmailStr
    roles: List[str] = [Roles.FORM_RESPONDER]
    plan: Optional[Plans] = Plans.FREE
    stripe_customer_id: Optional[str]
    stripe_payment_id: Optional[str]
    tags: List[str]
