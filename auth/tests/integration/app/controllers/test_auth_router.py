from auth.app.container import container

from common.models.user import User, UserInfo


class TestAuthRouter:
    def test_callback_returns_the_existing_user(self, app_runner):
        # given an existing user and a jwt token for their email (the callback
        # never creates accounts, #758: see test_provider_sign_in.py)
        user_email = "test@example.com"
        app_runner.portal.call(container.user_repository().save_user, user_email)
        jwt_token = container.jwt_service().encode(UserInfo(email=user_email))

        # when calling auth/callback
        response = app_runner.get("auth/callback", params={"jwt_token": jwt_token})

        # then Assert the user is returned, id exists and sub and email are same
        assert response.status_code == 200

        user = User(**response.json())
        assert user.id is not None
        assert user.sub == user_email
