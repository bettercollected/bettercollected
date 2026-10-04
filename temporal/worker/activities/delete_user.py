from temporalio import activity, workflow

from settings.application import settings

with workflow.unsafe.imports_passed_through():
    from wrappers.apm_wrapper import APMAsyncHttpClient


@activity.defn(name="delete_user")
async def delete_user(deletion_request: str):
    """``deletion_request`` is the backend-encrypted request naming the
    account; it is passed on as is (the backend decrypts and checks it)."""
    async with APMAsyncHttpClient("delete_user") as client:
        headers = {"api-key": settings.api_key, "X-User-Deletion": deletion_request}
        response = await client.delete(url=settings.server_url + "/auth/user", headers=headers)
        if response.status_code != 200:
            raise RuntimeError("Could not delete user")
        return "User Deleted Successfully"
