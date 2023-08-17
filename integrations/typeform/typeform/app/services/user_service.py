from http import HTTPStatus

import jwt
from jwt import InvalidSignatureError, ExpiredSignatureError
from starlette.requests import Request

from common.constants import MESSAGE_UNAUTHORIZED
from common.models.user import Credential, User
from typeform.app.exceptions import HTTPException
from typeform.app.repositories.credentials_repository import CredentialRepository
from typeform.config import settings


async def get_user_credential(request: Request) -> Credential:
    access_token = request.cookies.get("Authorization")
    if not access_token:
        raise HTTPException(status_code=HTTPStatus.UNAUTHORIZED, content="No Access Token provided.")
    try:
        jwt_response = jwt.decode(
            access_token, key=settings.AUTH_JWT_SECRET, algorithms=["HS256"]
        )
    except InvalidSignatureError | ExpiredSignatureError:
        raise HTTPException(status_code=HTTPStatus.UNAUTHORIZED, content="Invalid JWT Signature")
    user = User(**jwt_response)
    credential = await CredentialRepository.get_credential(user.sub)
    if not credential:
        raise HTTPException(HTTPStatus.UNAUTHORIZED, content=MESSAGE_UNAUTHORIZED)
    return credential
