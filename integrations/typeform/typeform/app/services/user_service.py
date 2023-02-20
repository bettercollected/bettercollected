import jwt
from starlette.requests import Request

from common.models.user import Credential, User
from typeform.app.exceptions import HTTPException
from typeform.app.repositories.credentials_repository import CredentialRepository
from typeform.config import settings


async def get_user_credential(request: Request) -> Credential:
    access_token = request.cookies.get("Authorization")
    if not access_token:
        raise HTTPException(401, "No Access Token provided.")
    jwt_response = jwt.decode(access_token, key=settings.AUTH_JWT_SECRET, algorithms=["HS256"])
    user = User(**jwt_response)
    credential = await CredentialRepository.get_credential(user.sub)
    return credential
