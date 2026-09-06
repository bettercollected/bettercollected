from auth.app.schemas.provider import Provider


class ProviderRepository:
    async def get_provider(self, provider_name: str) -> Provider:
        return await Provider.find_one_by_args(Provider.provider_name == provider_name)
