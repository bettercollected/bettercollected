import datetime as dt

from common.records import Record, RecordId
from pydantic import EmailStr


class PriceSuggestion(Record):
    user_id: RecordId
    email: EmailStr
    price: int

    class Settings:
        name = "price_suggestion"
        bson_encoders = {
            dt.datetime: lambda o: dt.datetime.isoformat(o),
            dt.date: lambda o: dt.date.isoformat(o),
            dt.time: lambda o: dt.time.isoformat(o),
        }
