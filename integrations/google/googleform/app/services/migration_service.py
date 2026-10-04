import requests
from loguru import logger

from googleform.app.containers import Container
from googleform.config import settings

INTERNAL_KEY_HEADER = "X-Internal-Key"


def auth_service_headers() -> dict:
    """Headers for a call to the auth service, whose API is internal: the
    shared key, only ever sent there."""
    key = settings.AUTH_INTERNAL_NOTIFY_KEY
    return {INTERNAL_KEY_HEADER: key} if key else {}


def log_if_internal_key_missing() -> bool:
    """Log an error at startup when the key is unset (True when set)."""
    if settings.AUTH_INTERNAL_NOTIFY_KEY:
        return True
    logger.error(
        "AUTH_INTERNAL_NOTIFY_KEY is not set: the auth service refuses this "
        "service's requests without it. Set the same value as on the backend "
        "and auth services."
    )
    return False


async def migrate_credentials_to_include_user_id():
    repository = Container.oauth_credential_repo()
    for credentials_document in await repository.list_all():
        if credentials_document.user_id is None:
            user_id = await fetch_user_id_for_email(email=credentials_document.email)
            if not user_id:
                return
            credentials_document.user_id = user_id
            await repository.save(credentials_document)


async def fetch_user_id_for_email(email: str):
    try:
        user_response = requests.get(
            f"{settings.AUTH_SERVER_URL}/users",
            params={"emails": [email]},
            headers=auth_service_headers(),
            timeout=30,
        )
        user_json = user_response.json()
        if len(user_json.get("users_info")) == 0:
            return
        return user_json.get("users_info")[0].get("_id")
    except Exception as e:
        return None
