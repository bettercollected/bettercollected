import datetime

import jwt
import loguru
from starlette.requests import Request

from common.models.user import User
from googleform.app.exceptions import HTTPException
from googleform.app.repositories.oauth_credential import OauthCredentialRepository
from googleform.app.schemas.oauth_credential import Oauth2CredentialDocument
from googleform.config import settings


async def get_user_credential(request: Request) -> Oauth2CredentialDocument:
    start_time = datetime.datetime.utcnow()
    access_token = request.cookies.get("Authorization")
    if not access_token:
        raise HTTPException(401, "No Access Token provided.")
    jwt_response = jwt.decode(
        access_token, key=settings.AUTH_JWT_SECRET, algorithms=["HS256"]
    )
    user = User(**jwt_response)
    credential = await OauthCredentialRepository().get(user.sub)
    loguru.logger.info(user.sub + ": Timer get_user_credential" + str(datetime.datetime.utcnow() - start_time))
    return credential
