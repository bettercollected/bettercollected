"""Time-based one-time passwords (moved to ``common.security.totp``).

Re-exported here so the admin portal's imports and tests keep working."""

from common.security.totp import (
    DIGITS,
    DRIFT_STEPS,
    SECRET_BYTES,
    STEP_SECONDS,
    code_at,
    current_code,
    decode_secret,
    generate_secret,
    hotp,
    next_last_used_step,
    otpauth_uri,
    step_for,
    verify,
)

__all__ = [
    "DIGITS",
    "DRIFT_STEPS",
    "SECRET_BYTES",
    "STEP_SECONDS",
    "code_at",
    "current_code",
    "decode_secret",
    "generate_secret",
    "hotp",
    "next_last_used_step",
    "otpauth_uri",
    "step_for",
    "verify",
]
