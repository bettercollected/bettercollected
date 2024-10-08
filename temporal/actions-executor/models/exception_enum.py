import enum


class ExceptionType(str, enum.Enum):
    GOOGLE_SHEET_MISSING: str = 'Google Sheet with given ID not found.'
    OAUTH_TOKEN_MISSING: str = 'Token has been expired or revoked.'
