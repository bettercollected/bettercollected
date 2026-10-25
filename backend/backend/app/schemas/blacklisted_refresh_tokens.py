import datetime as dt

from common.records import Record


class BlackListedRefreshTokens(Record):
    token: str
    expiry: dt.datetime

    class Settings:
        name = "blacklisted_refresh_tokens"
        bson_encoders = {
            dt.datetime: lambda o: dt.datetime.isoformat(o),
            dt.date: lambda o: dt.date.isoformat(o),
            dt.time: lambda o: dt.time.isoformat(o),
        }
