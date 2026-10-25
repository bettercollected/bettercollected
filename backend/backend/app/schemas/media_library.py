import datetime as dt
from backend.app.models.dtos.media_libraries_dto import MediaLibrary
from common.records import Record


class MediaLibraryDocument(Record, MediaLibrary):

    class Settings:
        name = "media_libraries"
        bson_encoders = {
            dt.datetime: lambda o: dt.datetime.isoformat(o),
            dt.date: lambda o: dt.date.isoformat(o),
            dt.time: lambda o: dt.time.isoformat(o),
        }
