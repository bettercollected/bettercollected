import json

import httpx
import loguru
from aiokafka import AIOKafkaProducer
from aiokafka.errors import KafkaConnectionError
from pydantic import BaseModel

from backend.app.models.dtos.kafka_event_dto import KafkaEventType, KafkaEventDto
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
        self.producer: AIOKafkaProducer = AIOKafkaProducer(bootstrap_servers=settings.kafka_settings.server_url,
                                                           value_serializer=value_serializer)

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

    async def send_event(self, event_type: KafkaEventType, user_id: str):
        event_message = KafkaEventDto(event_type=event_type, user_id=user_id)
        if settings.kafka_settings.enabled:
            try:
                await self.producer.send_and_wait(settings.kafka_settings.topic, event_message)
            except Exception as e:
                loguru.logger.warning("Could not send event to kafka, Event Message: " + str(event_message.dict()))

        if settings.event_webhook_settings.enabled:
            try:
                await httpx.AsyncClient().post(
                    settings.event_webhook_settings.url,
                    json={
                        "embeds": [
                            {
                                "fields": [
                                    {
                                        "name": "Event Type",
                                        "value": event_type,
                                        "inline": True
                                    },
                                    {
                                        "name": "User Id",
                                        "value": user_id,
                                        "inline": True
                                    }
                                ]
                            }

                        ]
                    }
                )
            except Exception as e:
                loguru.logger.warning("Could not send event to Webhook, Event Message: " + str(event_message.dict()))


event_logger_service = KafkaService()
