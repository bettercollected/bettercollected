"""The admin portal's security modules re-export the shared primitives, so the
two services cannot drift apart."""

from backend.admin.security import clock as admin_clock
from backend.admin.security import recovery as admin_recovery
from backend.admin.security import totp as admin_totp
from common.security import clock, recovery, totp


def test_totp_is_the_shared_implementation():
    for name in admin_totp.__all__:
        assert getattr(admin_totp, name) is getattr(totp, name)


def test_clock_is_the_shared_implementation():
    for name in admin_clock.__all__:
        assert getattr(admin_clock, name) is getattr(clock, name)


def test_recovery_code_shape_is_the_shared_implementation():
    for name in ("generate_code", "is_well_formed", "normalise"):
        assert getattr(admin_recovery, name) is getattr(recovery, name)
    for name in ("CODE_COUNT", "CODE_CHARS", "GROUP"):
        assert getattr(admin_recovery, name) == getattr(recovery, name)
