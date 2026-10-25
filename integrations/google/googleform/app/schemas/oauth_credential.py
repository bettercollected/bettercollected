import datetime as dt
from typing import Optional

from common.records import Record
from googleform.app.models.oauth_credential import GoogleCredentialResponse


# One account's Google OAuth credential, stored in google.oauth_credentials. No
# docstring: it would become the class's JSON schema description. ``credentials``
# holds the encrypted tokens (bytes) once stored, the decrypted
# GoogleCredentialResponse only in memory.
class Oauth2CredentialDocument(Record):
    user_id: Optional[str] = None
    email: Optional[str] = None
    state: Optional[str] = None
    provider: Optional[str] = None
    credentials: Optional[GoogleCredentialResponse] | bytes = None

    class Settings:
        name = "Oauth2CredentialDocument"
        bson_encoders = {
            dt.datetime: lambda o: dt.datetime.isoformat(o),
            dt.date: lambda o: dt.date.isoformat(o),
            dt.time: lambda o: dt.time.isoformat(o),
        }
