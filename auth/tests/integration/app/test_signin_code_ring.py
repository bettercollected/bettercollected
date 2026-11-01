"""Sign-in codes under a key ring (docs/auth-key-rotation.md): hashed with the
current member of ``AUTH_AES_HEX_KEY``, accepted under any member, so a code
pending at a promotion stays valid. Throwaway keys only."""

import calendar
import datetime as dt

from cryptography.fernet import Fernet

from auth.app.services import signin_code

OLD = Fernet.generate_key().decode()
NEW = Fernet.generate_key().decode()
ACCOUNT = "6a0000000000000000000001"
CODE = "ABC-123"


def epoch(minutes: int = 5) -> int:
    later = dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=minutes)
    return calendar.timegm(later.utctimetuple())


def stored_under(secret: str, expiry: int) -> signin_code.StoredCode:
    value = signin_code.stored(signin_code.digest(CODE, ACCOUNT, "creator", expiry, secret=secret))
    return signin_code.parse(value)


def test_a_code_pending_across_the_rotation_stays_valid_until_the_old_key_is_dropped():
    expiry = epoch()
    pending = stored_under(OLD, expiry)  # sent before the promotion
    for ring in (OLD, f"{OLD},{NEW}", f"{NEW},{OLD}"):
        assert signin_code.matches(pending, CODE, ACCOUNT, "creator", expiry, secret=ring), ring
    assert not signin_code.matches(pending, CODE, ACCOUNT, "creator", expiry, secret=NEW)


def test_new_codes_use_the_first_member():
    expiry = epoch()
    fresh = stored_under(f"{NEW},{OLD}", expiry)
    assert signin_code.matches(fresh, CODE, ACCOUNT, "creator", expiry, secret=NEW)
    assert not signin_code.matches(fresh, CODE, ACCOUNT, "creator", expiry, secret=OLD)
    assert signin_code.digest(CODE, ACCOUNT, "creator", expiry, secret=f"{NEW},{OLD}") == signin_code.digest(
        CODE, ACCOUNT, "creator", expiry, secret=NEW
    )


def test_a_wrong_code_account_purpose_or_expiry_matches_under_no_member():
    expiry = epoch()
    pending = stored_under(f"{NEW},{OLD}", expiry)
    ring = f"{NEW},{OLD}"
    assert not signin_code.matches(pending, "WRONG", ACCOUNT, "creator", expiry, secret=ring)
    assert not signin_code.matches(pending, CODE, "6a0000000000000000000002", "creator", expiry, secret=ring)
    assert not signin_code.matches(pending, CODE, ACCOUNT, "respondent", expiry, secret=ring)
    assert not signin_code.matches(pending, CODE, ACCOUNT, "creator", expiry + 1, secret=ring)
