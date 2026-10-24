import datetime as dt

from backend.app.models.form_plugin_config import FormProviderConfigDto
from common.records import Record


class FormPluginConfigDocument(Record, FormProviderConfigDto):
    class Settings:
        name = "forms_plugin_configs"
        bson_encoders = {
            dt.datetime: lambda o: dt.datetime.isoformat(o),
            dt.date: lambda o: dt.date.isoformat(o),
            dt.time: lambda o: dt.time.isoformat(o),
        }
