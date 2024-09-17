import datetime as dt
from backend.app.models.dtos.media_libraries_dto import MediaLibrary
from common.configs.mongo_document import MongoDocument
from backend.app.handlers.database import entity


@entity
class MediaLibraryDocument(MongoDocument, MediaLibrary):

    class Settings:
        name = "media_libraries"
        bson_encoders = {
            dt.datetime: lambda o: dt.datetime.isoformat(o),
            dt.date: lambda o: dt.date.isoformat(o),
            dt.time: lambda o: dt.time.isoformat(o),
        }
