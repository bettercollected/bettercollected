import json

import httpx
import loguru
from aiokafka import AIOKafkaProducer
from aiokafka.errors import KafkaConnectionError
from pydantic import BaseModel, EmailStr

from backend.app.models.dtos.kafka_event_dto import UserEventType, UserEventDto
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


class KafkaService:
    def __init__(self):
        if settings.kafka_settings.enabled:
            self.producer: AIOKafkaProducer = AIOKafkaProducer(
                bootstrap_servers=settings.kafka_settings.server_url,
                value_serializer=value_serializer,
            )

    async def start_kafka_producer(self):
        try:
            loguru.logger.info("Starting kafka producer")
            await self.producer.start()
        except KafkaConnectionError as e:
            loguru.logger.info("Could not connect to Kafka service")

    async def stop_kafka_producer(self):
        try:
            loguru.logger.info("Stopping kafka producer")
            await self.producer.stop()
        except KafkaConnectionError as e:
            loguru.logger.info("Could not connect to Kafka service")

    async def send_event(
        self, event_type: UserEventType, user_id: str, email: EmailStr
    ):
        event_message = UserEventDto(
            event_type=event_type, user_id=user_id, email=email
        )
        if settings.kafka_settings.enabled:
            try:
                await self.producer.send_and_wait(
                    settings.kafka_settings.topic, event_message
                )
            except Exception as e:
                loguru.logger.warning(
                    "Could not send event to kafka, Event Message: "
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


event_logger_service = KafkaService()
