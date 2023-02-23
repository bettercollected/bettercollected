from auth.app.services.base_auth_provider import BaseAuthProvider


class TypeformAuthProvider(BaseAuthProvider):
    async def get_basic_auth_url(self, client_referer_url: str) -> str:
        pass

    async def basic_auth_callback(self, code: str, *args, **kwargs) -> (bool, str):
        pass
