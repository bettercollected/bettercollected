from http import HTTPStatus

import jwt
from starlette.requests import Request

from googleform.app.exceptions import HTTPException
from googleform.app.repositories.oauth_credential import OauthCredentialRepository
from googleform.app.schemas.oauth_credential import Oauth2CredentialDocument
from googleform.config import settings


async def get_user_credential(request: Request) -> Oauth2CredentialDocument:
    access_token = request.cookies.get("Authorization")
    if not access_token:
        raise HTTPException(401, "No Access Token provided.")
    jwt_response = jwt.decode(
        access_token, key=settings.AUTH_JWT_SECRET, algorithms=["HS256"]
    )
    credential = await OauthCredentialRepository().get(jwt_response.get("sub"))
    if not credential:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, content="Credentials for user not found")
    return credential
