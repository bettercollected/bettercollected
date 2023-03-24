import datetime as dt

from common.configs.mongo_document import MongoDocument


class AllowedOriginsDocument(MongoDocument):
    """A custom MongoDocument subclass representing a document in the
    'allowedOrigins' collection.

    Attributes:
        origin (str): The origin of the document.

    Class Attributes:
        Collection: A nested class that defines the name of the collection
            for this document type.
        Settings: A nested class that defines the name of the settings for
            this document type, as well as bson encoder functions for
            certain datetime objects.
    """

    origin: str

    class Settings:
        name = "allowed_origins"
        bson_encoders = {
            dt.datetime: lambda o: dt.datetime.isoformat(o),
            dt.date: lambda o: dt.date.isoformat(o),
            dt.time: lambda o: dt.time.isoformat(o),
        }
