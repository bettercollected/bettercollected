import datetime as dt

from backend.app.core.form_plugin_config import FormProvider
from common.configs.mongo_document import MongoDocument


class FormPluginConfigDocument(MongoDocument, FormProvider):
    class Settings:
        name = "forms_plugin_configs"
        bson_encoders = {
            dt.datetime: lambda o: dt.datetime.isoformat(o),
            dt.date: lambda o: dt.date.isoformat(o),
            dt.time: lambda o: dt.time.isoformat(o),
        }
