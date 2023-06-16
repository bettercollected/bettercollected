import requests
from temporalio import activity, workflow

from models.user_tokens import UserTokens
from settings.application import settings

workflow.unsafe.imports_passed_through()


@activity.defn(name="delete_user")
async def delete_user(user_token: UserTokens):
    cookies = {"Authorization": user_token.access_token, "RefreshToken": user_token.refresh_token}
    response = requests.delete(url=settings.server_url + "/auth/user", cookies=cookies)
    if response.status_code != 200:
        raise RuntimeError("Could not delete user")
    return "User Deleted Successfully"
