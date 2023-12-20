import json

import loguru
from aiokafka import AIOKafkaProducer
from aiokafka.errors import KafkaConnectionError
from pydantic import BaseModel

from backend.app.models.dtos.kafka_event_dto import KafkaEventDto
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

    async def send_event(self, event_message: KafkaEventDto):
        if not settings.kafka_settings.enabled:
            return
        try:
            await self.producer.send_and_wait(settings.kafka_settings.topic, event_message)
        except Exception as e:
            loguru.logger.warning("Could not send event to kafka, Event Message: " + str(event_message.dict()))


kafka_service = KafkaService()
