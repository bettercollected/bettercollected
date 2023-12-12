import httpx

from configs.elastic_apm import apm_client


class APMAsyncHttpClient:
    def __init__(self, transaction_name):
        self.apm_client = apm_client
        self.transaction_type = "script"
        self.transaction_name = transaction_name

    async def __aenter__(self):
        if self.apm_client is not None:
            self.apm_client.begin_transaction(transaction_type=self.transaction_type)
        self.client = httpx.AsyncClient(timeout=60)
        return self.client

    async def __aexit__(self, exc_type, exc, tb):
        await self.client.aclose()  # Ensure the AsyncClient is closed
        if self.apm_client is not None:
            transaction_result = "success" if exc_type is None else "failure"
            self.apm_client.end_transaction(name=self.transaction_name, result=transaction_result)
