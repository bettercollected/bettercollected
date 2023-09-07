import json

from temporalio import activity, workflow

from models.delete_response import DeleteResponseParams
from settings.application import settings
import requests
from configs.crypto import crypto
from models.user_tokens import UserTokens


@activity.defn(name="delete_response")
async def delete_response(delete_response_params: DeleteResponseParams):
    headers = {"api_key": settings.api_key}
    response = requests.post(
        url=settings.server_url
            + f"/temporal/submissions/{delete_response_params.response_id}",
        headers=headers
    )
