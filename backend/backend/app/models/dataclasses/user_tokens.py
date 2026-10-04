from dataclasses import dataclass


@dataclass
class UserTokens:
    access_token: str
    refresh_token: str


@dataclass
class UserDeletion:
    """Whose account a deletion job deletes. Travels encrypted with the
    backend's key (the job's ``encrypted_tokens`` argument / the Temporal
    workflow input), which is what proves the backend queued it."""

    user_id: str
    email: str
