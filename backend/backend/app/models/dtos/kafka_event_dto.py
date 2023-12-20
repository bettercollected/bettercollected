import enum

from pydantic import BaseModel


class KafkaEventType(str, enum.Enum):
    USER_CREATED = "user_created"
    FORM_IMPORTED = "form_imported"
    SLUG_CHANGED = "slug_changed"
    ACCOUNT_DELETED = "account_deleted"
    USER_UPGRADED_TO_PRO = "user_upgraded_to_pro"
    CUSTOM_DOMAIN_CHANGED = "custom_domain_changed"


class KafkaEventDto(BaseModel):
    event_type: KafkaEventType
    user_id: str
