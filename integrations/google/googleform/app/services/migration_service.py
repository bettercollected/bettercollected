import requests

from googleform.app.schemas.oauth_credential import Oauth2CredentialDocument
from googleform.config import settings


async def migrate_credentials_to_include_user_id():
    credentials_documents = await Oauth2CredentialDocument.find().to_list()
    for credentials_document in credentials_documents:
        if credentials_document.user_id is None:
            user_id = await fetch_user_id_for_email(email=credentials_document.email)
            if not user_id:
                return
            credentials_document.user_id = user_id
            await credentials_document.save()


async def fetch_user_id_for_email(email: str):
    try:
        user_response = requests.get(
            f"{settings.AUTH_SERVER_URL}/users", params={"emails": [email]}
        )
        user_json = user_response.json()
        if len(user_json.get("users_info")) == 0:
            return
        return user_json.get("users_info")[0].get("_id")
    except Exception as e:
        return None
