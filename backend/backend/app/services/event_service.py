"""Platform events (sign-up, upgrade, account deletion, ...) posted to the
operator's event webhook (``EVENT_WEBHOOK_URL``, off unless
``EVENT_WEBHOOK_ENABLED``). The payload carries the event type and the user id
only, never an email address or other personal data."""

import asyncio

import httpx
import loguru

from backend.app.models.dtos.event_dto import UserEventType
from backend.config import settings


class EventService:
    # a seam for tests: the HTTP transport of the webhook (tests never reach
    # a real webhook)
    transport = None

    async def post_event(self, event_type: UserEventType, user_id: str):
        if settings.event_webhook_settings.enabled:
            try:
                async with httpx.AsyncClient(transport=self.transport) as client:
                    await client.post(
                        settings.event_webhook_settings.url,
                        json=webhook_payload(event_type, user_id),
                    )
            except Exception:
                loguru.logger.warning(
                    f"Could not send event to Webhook: {event_type} for user {user_id}"
                )

        loguru.logger.info(f"Event handled: {event_type} for user {user_id}")

    async def send_event(self, event_type: UserEventType, user_id: str):
        asyncio.ensure_future(self.post_event(event_type, user_id))


def webhook_payload(event_type: UserEventType, user_id) -> dict:
    return {
        "content": get_enthusiastic_text(event_type=event_type),
        "embeds": [
            {
                "fields": [
                    {"name": "Event Type", "value": event_type, "inline": True},
                    {"name": "", "value": "", "inline": True},
                    {"name": "User Id", "value": str(user_id), "inline": True},
                ]
            }
        ],
    }


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


event_logger_service = EventService()
