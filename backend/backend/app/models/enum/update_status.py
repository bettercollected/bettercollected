import enum


class UpdateStatus(str, enum.Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    INVALID_GRANT = "INVALID_GRANT"
    NOT_FOUND = "NOT_FOUND"
