import datetime as dt
from typing import Dict, Any

from beanie import PydanticObjectId
from common.configs.mongo_document import MongoDocument

from backend.app.handlers.database import entity


@entity
class CreateFormPrompt(MongoDocument):
    prompt: str
    openai_response: Dict[str, Any]
    created_form: Dict[str, Any]
    form_id: PydanticObjectId

    class Settings:
        name = "create_form_prompts"
        bson_encoders = {
            dt.datetime: lambda o: dt.datetime.isoformat(o),
            dt.date: lambda o: dt.date.isoformat(o),
            dt.time: lambda o: dt.time.isoformat(o),
        }
