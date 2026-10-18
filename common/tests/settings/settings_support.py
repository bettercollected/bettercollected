import base64
from datetime import datetime, timezone

from common.settings.canonical import SettingRow
from common.settings.keys import SectionKeys

MASTER_BYTES = bytes(range(48))
MASTER = base64.b64encode(MASTER_BYTES).decode()
OTHER_MASTER = base64.b64encode(bytes(range(1, 49))).decode()
MOMENT = datetime(2026, 10, 18, 12, 30, 5, 123456, tzinfo=timezone.utc)


def plain_row(**changes) -> SettingRow:
    fields = dict(
        key="MAIL_SMTP_PORT",
        section="mail",
        readers=("backend", "auth"),
        is_secret=False,
        reload_class="R",
        version=3,
        updated_at=MOMENT,
        value=587,
    )
    fields.update(changes)
    return SettingRow(**fields)


def secret_row(keys: SectionKeys, plaintext="smtp-pass-1", version=1) -> SettingRow:
    blob = keys.seal("mail", "MAIL_PASSWORD", version, plaintext)
    return SettingRow(
        key="MAIL_PASSWORD",
        section="mail",
        readers=("backend", "auth"),
        is_secret=True,
        reload_class="R",
        version=version,
        updated_at=MOMENT,
        blob=blob,
    )
