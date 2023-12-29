import enum

from pydantic import BaseModel


class UserEventType(str, enum.Enum):
    USER_CREATED = "user_created"
    FORM_IMPORTED = "form_imported"
    SLUG_CHANGED = "slug_changed"
    ACCOUNT_DELETED = "account_deleted"
    USER_UPGRADED_TO_PRO = "user_upgraded_to_pro"
    USER_DOWNGRADED = "user_downgraded"
    CUSTOM_DOMAIN_CHANGED = "custom_domain_changed"


class UserEventDto(BaseModel):
    event_type: UserEventType
    user_id: str
