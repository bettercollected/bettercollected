import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote

import httpx
import loguru
from pydantic import BaseModel, EmailStr

from backend.app.models.dtos.brevo_event_dto import UserEventType
from backend.config import settings


def value_serializer(model_instance):
    if isinstance(model_instance, BaseModel):
        data_dict = model_instance.model_dump(mode="json")
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

# Brevo's REST API (contacts); the tracker uses BREVO_TRACKER_API_URL
BREVO_API_URL = "https://api.brevo.com/v3"
ERASURE_ATTEMPTS = 4
ERASURE_BACKOFF_SECONDS = 1.0


class BrevoService:
    # a seam for tests: the HTTP transport of the contacts API (tests never
    # reach Brevo)
    contacts_transport = None
    # and of the pause between erasure attempts
    retry_sleep = staticmethod(asyncio.sleep)

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
        # A deleted account's email address must not be sent anywhere.
        if event_type != UserEventType.ACCOUNT_DELETED:
            try:
                await self.track_event(email=email, event_type=event_type)
            except Exception:
                loguru.logger.warning(
                    f"Could not send event to Brevo: {event_type} for user {user_id}"
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
            except Exception:
                loguru.logger.warning(
                    f"Could not send event to Webhook: {event_type} for user {user_id}"
                )

        loguru.logger.info(f"Event handled: {event_type} for user {user_id}")

    async def send_event(
        self, event_type: UserEventType, user_id: str, email: EmailStr
    ):
        asyncio.ensure_future(self.send_brevo_event(event_type, user_id, email))

    async def delete_contact(self, email: str, user_id: str) -> str:
        """Erase a deleted account's Brevo contact (GDPR erasure) with the
        contacts API key (``BREVO_CONTACTS_API_KEY``), never the tracker key.
        Best effort: returns ``deleted``, ``absent`` (Brevo has no such
        contact), ``skipped`` (no key) or ``failed``. Logs the user id and the
        outcome, never the address."""
        key = settings.brevo_settings.contacts_api_key
        if not key:
            loguru.logger.info(
                f"Brevo contact erasure skipped for user {user_id}: "
                "BREVO_CONTACTS_API_KEY is not set"
            )
            return "skipped"
        if not email or not email.strip():
            return "absent"
        # once the account is gone the address is too: a transient failure
        # (rate limit, Brevo down) is retried a few times with backoff
        path = f"{BREVO_API_URL}/contacts/{quote(email.strip().lower(), safe='')}"
        outcome = problem = None
        for attempt in range(1, ERASURE_ATTEMPTS + 1):
            if attempt > 1:
                await self.retry_sleep(ERASURE_BACKOFF_SECONDS * 2 ** (attempt - 2))
            try:
                async with httpx.AsyncClient(
                    transport=self.contacts_transport, timeout=15
                ) as client:
                    response = await client.delete(
                        path,
                        params={"identifierType": "email_id"},
                        headers={"api-key": key, "accept": "application/json"},
                    )
            except httpx.HTTPError as error:
                problem = type(error).__name__
                continue
            if response.status_code in (200, 204):
                outcome = "deleted"
                break
            if response.status_code == 404:
                outcome = "absent"
                break
            problem = f"HTTP {response.status_code}"
            if response.status_code != 429 and response.status_code < 500:
                break  # refused (a wrong key, say): retrying will not help
        if outcome is None:
            loguru.logger.warning(
                f"Brevo contact erasure failed for user {user_id}: {problem}"
            )
            return "failed"
        loguru.logger.info(f"Brevo contact erasure for user {user_id}: {outcome}")
        return outcome


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
