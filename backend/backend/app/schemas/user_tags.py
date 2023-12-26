from common.configs.mongo_document import MongoDocument

from backend.app.handlers.database import entity
from backend.app.models.user_tags import UserTags


@entity
class UserTagsDocument(MongoDocument, UserTags):
    class Settings:
        name = "user_tags"
