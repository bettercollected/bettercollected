from temporalio import activity, workflow

from models.user_tokens import UserTokens
from settings.application import settings

with workflow.unsafe.imports_passed_through():
    import requests


@activity.defn(name="delete_user")
async def delete_user(user_token: UserTokens):
    cookies = {"Authorization": user_token.access_token, "RefreshToken": user_token.refresh_token}
    headers = {"api_key": settings.api_key}
    response = requests.delete(url=settings.server_url + "/auth/user", cookies=cookies, headers=headers)
    if response.status_code != 200:
        raise RuntimeError("Could not delete user")
    return "User Deleted Successfully"
