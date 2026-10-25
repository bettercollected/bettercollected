from common.records import Record

from backend.app.models.user_tags import UserTags


class UserTagsDocument(Record, UserTags):
    class Settings:
        name = "user_tags"
