import jwt

from common.models.user import Credential
from typeform.config import settings


def get_user_credential(jwt_token: str) -> Credential:
    jwt_response = jwt.decode(jwt_token,
                              key=settings.JWT_SECRET,
                              algorithms=["HS256"]
                              )
    credential = Credential(**jwt_response)
    return credential
