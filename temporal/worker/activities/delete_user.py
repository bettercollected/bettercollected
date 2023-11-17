import json

from temporalio import activity, workflow

from settings.application import settings

with workflow.unsafe.imports_passed_through():
    import httpx
    from configs.crypto import crypto
    from models.user_tokens import UserTokens


@activity.defn(name="delete_user")
async def delete_user(token: str):
    async with httpx.AsyncClient() as client:
        decrypted_token = crypto.decrypt(token)
        user_token = UserTokens(**json.loads(decrypted_token))
        cookies = {"Authorization": user_token.access_token, "RefreshToken": user_token.refresh_token}
        headers = {"api-key": settings.api_key}
        response = await  client.delete(url=settings.server_url + "/auth/user", cookies=cookies, headers=headers)
        if response.status_code != 200:
            raise RuntimeError("Could not delete user")
        return "User Deleted Successfully"
