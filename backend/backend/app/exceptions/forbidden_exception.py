from http import HTTPStatus

from backend.app.exceptions import HTTPException


class ForbiddenException(HTTPException):
    def __init__(self, content="You are not authorized.", headers=None):
        super().__init__(
            status_code=HTTPStatus.FORBIDDEN, content=content, headers=headers
        )
