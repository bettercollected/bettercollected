from typing import Optional, List

from beanie import PydanticObjectId
from pydantic import EmailStr, BaseModel

from common.enums.plan import Plans
from common.enums.roles import Roles


class UserInfoDto(BaseModel):
    id: PydanticObjectId = None
    _id: str
    first_name: Optional[str]
    last_name: Optional[str]
    profile_image: Optional[str]
    email: EmailStr
    roles: List[str] = [Roles.FORM_RESPONDER]
    plan: Optional[Plans] = Plans.FREE
    stripe_customer_id: Optional[str]
    stripe_payment_id: Optional[str]

    def __init__(self, _id="", **kwargs):
        super().__init__(**kwargs)
        self.id = PydanticObjectId(_id)
