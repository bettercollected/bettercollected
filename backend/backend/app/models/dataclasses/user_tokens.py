from dataclasses import dataclass


@dataclass
class UserTokens:
    access_token: str
    refresh_token: str
