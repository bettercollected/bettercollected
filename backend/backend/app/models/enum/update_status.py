import enum


class UpdateStatus(str, enum.Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    INVALID_GRANT = "INVALID_GRANT"
    REVOKED = "REVOKED"
    NOT_FOUND = "NOT_FOUND"
