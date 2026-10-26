"""The Beanie class of auth's account document, frozen as it was before 4.1
moved it to ``Record`` (test support; removed together with Beanie).

It is the reference of the wire check in ``test_record_codec_golden.py``:
``auth.app.schemas.user.UserDocument`` must describe itself (JSON schema) and
serialise every pinned document exactly as this class did. It is set up
offline (no Mongo server): the check only builds and dumps instances.
"""

import datetime as dt
from typing import Annotated, List, Optional

from beanie import Indexed
from common.db.beanie_bridge import MongoDocument, init_documents, offline_client
from common.enums.plan import Plans


class UserDocument(MongoDocument):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    profile_image: Optional[str] = None
    email: Annotated[str, Indexed(unique=True)]
    roles: Optional[List[str]] = []
    otp_code: Optional[str] = None
    otp_expiry: Optional[int] = None
    otp_code_for: Optional[str] = None
    plan: Optional[Plans] = Plans.FREE
    stripe_customer_id: Optional[str] = None
    stripe_payment_id: Optional[str] = None
    last_logged_in: Optional[dt.datetime] = None

    class Settings:
        name = "users"
        bson_encoders = {
            dt.datetime: lambda o: dt.datetime.isoformat(o),
            dt.date: lambda o: dt.date.isoformat(o),
            dt.time: lambda o: dt.time.isoformat(o),
        }


ORIGINALS = (UserDocument,)


async def init_originals() -> None:
    """Beanie's class set-up without a server (a client that never connects)."""
    client = offline_client()
    await init_documents(client["auth_originals"], list(ORIGINALS), required=False)
