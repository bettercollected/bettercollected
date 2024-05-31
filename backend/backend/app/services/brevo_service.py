import asyncio
import json
from concurrent.futures import ThreadPoolExecutor

import httpx
import loguru
from pydantic import BaseModel, EmailStr

from backend.app.models.dtos.brevo_event_dto import UserEventDto, UserEventType
from backend.config import settings


def value_serializer(model_instance):
    if isinstance(model_instance, BaseModel):
        data_dict = model_instance.dict()
        try:
            serialized_data = json.dumps(data_dict)
            return serialized_data.encode("utf-8")
        except Exception as e:
            print(f"Serialization error: {e}")
            return None
    else:
        print("Invalid input. Please provide an instance of a Pydantic BaseModel.")
        return None


executor = ThreadPoolExecutor(max_workers=10)


class BrevoService:
    def __init__(self):
        self.event_api_client = httpx.AsyncClient(
            headers={
                "accept": "application/json",
                "content-type": "application/json",
                "ma-key": settings.brevo_settings.tracker_key,
            }
        )

    async def track_event(self, email: EmailStr, event_type: UserEventType):
        return await self.event_api_client.post(
            settings.brevo_settings.tracker_api_url,
            json={"email": email, "event": event_type},
        )

    async def send_brevo_event(
        self, event_type: UserEventType, user_id: str, email: EmailStr
    ):
        event_message = UserEventDto(
            event_type=event_type, user_id=user_id, email=email
        )
        try:
            await self.track_event(email=email, event_type=event_type)
        except Exception as e:
            loguru.logger.warning(
                "Could not send event to Brevo, Event Message: "
                + str(event_message.dict())
            )

        if settings.event_webhook_settings.enabled:
            try:
                await httpx.AsyncClient().post(
                    settings.event_webhook_settings.url,
                    json={
                        "content": get_enthusiastic_text(event_type=event_type),
                        "embeds": [
                            {
                                "fields": [
                                    {
                                        "name": "Event Type",
                                        "value": event_type,
                                        "inline": True,
                                    },
                                    {"name": "", "value": "", "inline": True},
                                    {
                                        "name": "User Id",
                                        "value": user_id,
                                        "inline": True,
                                    },
                                ]
                            }
                        ],
                    },
                )
            except Exception as e:
                loguru.logger.warning(
                    "Could not send event to Webhook, Event Message: "
                    + str(event_message.dict())
                )

        loguru.logger.info("Event Handled Successfully", event_type, user_id)

    async def send_event(
        self, event_type: UserEventType, user_id: str, email: EmailStr
    ):
        asyncio.ensure_future(self.send_brevo_event(event_type, user_id, email))


def get_enthusiastic_text(event_type):
    enthusiastic_texts = {
        UserEventType.USER_CREATED: "Awesome! A new user has joined us!",
        UserEventType.FORM_IMPORTED: "Exciting news! A form has been imported.",
        UserEventType.SLUG_CHANGED: "Wow! The slug of a form has been changed.",
        UserEventType.ACCOUNT_DELETED: "Oh no! An account has been deleted.",
        UserEventType.USER_UPGRADED_TO_PRO: "Fantastic! A user has upgraded to Pro.",
        UserEventType.USER_DOWNGRADED: "Oops! A user has been downgraded.",
        UserEventType.CUSTOM_DOMAIN_CHANGED: "Amazing! The custom domain has been changed.",
    }

    if event_type in enthusiastic_texts:
        return enthusiastic_texts[event_type]
    else:
        return "Unknown event type. Enthusiasm can't contain the unknown!"


event_logger_service = BrevoService()
