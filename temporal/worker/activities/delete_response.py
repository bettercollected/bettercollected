import json

from temporalio import activity, workflow

from settings.application import settings
import requests
from configs.crypto import crypto
from models.user_tokens import UserTokens


@activity.defn(name="delete_response")
async def delete_user(token: str):
    decrypted_token = crypto.decrypt(token)
    user_token = UserTokens(**json.loads(decrypted_token))
    cookies = {"Authorization": user_token.access_token, "RefreshToken": user_token.refresh_token}
    headers = {"api_key": settings.api_key}
    response = requests.delete(url=settings.server_url + "/auth/user", cookies=cookies, headers=headers)
    if response.status_code != 200:
        raise RuntimeError("Could not delete user")
    return "User Deleted Successfully"
