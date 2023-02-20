import logging
import traceback

import jwt
from starlette.requests import Request

from backend.app.exceptions import HTTPException
from common.models.user import User

from backend.config import settings


def get_logged_user(request: Request) -> User:
    try:
        jwt_response = jwt.decode(
            request.cookies.get("Authorization"),
            key=settings.JWT_SECRET,
            algorithms=["HS256"],
        )
        user = User(**jwt_response)
        return user
    # TODO : Handle specific exceptions
    except Exception as e:
        logging.error(traceback.format_exc())
        raise HTTPException(401, "No user logged in.")
