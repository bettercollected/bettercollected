from typing import Tuple

import jwt

from backend.app.services import workspace_service
from backend.config import settings
from common.models.user import User, OAuthState


async def handle_backend_auth_callback(jwt_token: str) -> Tuple[User, OAuthState]:
    jwt_response = jwt.decode(jwt_token,
                              key=settings.JWT_SECRET,
                              algorithms=["HS256"]
                              )
    user = User(**jwt_response.get("user"))
    await workspace_service.create_workspace(user)
    state = OAuthState(**jwt_response.get("oauth_state"))
    return user, state
