from http import HTTPStatus

from common.services.jwt_service import decode_access_token
from jwt import PyJWTError
from starlette.requests import Request

from googleform.app.containers import Container
from googleform.app.exceptions import HTTPException
from googleform.app.schemas.oauth_credential import Oauth2CredentialDocument
from googleform.config import settings


async def get_user_credential(request: Request) -> Oauth2CredentialDocument:
    access_token = request.cookies.get("Authorization")
    if not access_token:
        raise HTTPException(401, "No Access Token provided.")
    try:
        jwt_response = decode_access_token(
            access_token, settings.AUTH_JWT_SECRET, algorithms=["HS256"]
        )
    except PyJWTError:
        raise HTTPException(
            status_code=HTTPStatus.UNAUTHORIZED, content="Invalid JWT Signature"
        )
    credential = await Container.oauth_credential_repo().get(jwt_response.get("sub"))
    if not credential:
        raise HTTPException(
            status_code=HTTPStatus.UNAUTHORIZED,
            content="Credentials for user not found",
        )
    return credential
