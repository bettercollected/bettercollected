from auth.app.container import container

from common.models.user import User, UserInfo


class TestAuthRouter:
    def test_should_user_created_when_callback_called(self, app_runner):
        # given user email and jwt token
        user_email = "test@example.com"
        jwt_token = container.jwt_service().encode(UserInfo(email=user_email))

        # when calling auth/callback
        response = app_runner.get("auth/callback", params={"jwt_token": jwt_token})

        # then Assert User is created in database, id exists and sub and email are same
        assert response.status_code == 200

        user = User(**response.json())
        assert user.id is not None
        assert user.sub == user_email
