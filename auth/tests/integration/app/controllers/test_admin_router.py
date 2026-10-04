"""GET /admin/metrics: user counts for the platform metrics dashboard, for a
Bearer token carrying the ADMIN role only."""

import datetime as dt

from auth.app.container import container
from common.models.user import User

URL = "admin/metrics"
PARAMS = {"first_week": "2026-03-02", "weeks": 3}


def bearer(**claims) -> dict:
    user = User(id="5f0000000000000000000000", sub="someone@example.com", **claims)
    return {"Authorization": f"Bearer {container.jwt_service().encode(user)}"}


class TestAdminRouter:
    def test_requires_a_token(self, app_runner):
        assert app_runner.get(URL, params=PARAMS).status_code == 401
        response = app_runner.get(
            URL, params=PARAMS, headers={"Authorization": "Bearer not-a-jwt"}
        )
        assert response.status_code == 401

    def test_requires_the_admin_role(self, app_runner):
        response = app_runner.get(
            URL, params=PARAMS, headers=bearer(roles=["FORM_CREATOR", "FORM_RESPONDER"])
        )
        assert response.status_code == 403

    def test_admin_gets_user_counts(self, app_runner):
        # the counts themselves are covered per store in test_postgres_parity
        response = app_runner.get(URL, params=PARAMS, headers=bearer(roles=["ADMIN"]))
        assert response.status_code == 200
        body = response.json()
        assert set(body) == {
            "total",
            "new_last_30_days",
            "active_last_30_days",
            "by_plan",
            "weekly_new",
        }
        assert set(body["by_plan"]) == {"FREE", "PRO"}
        assert sum(body["by_plan"].values()) == body["total"]
        assert body["new_last_30_days"] <= body["total"]
        assert [w["week_start"] for w in body["weekly_new"]] == [
            "2026-03-02",
            "2026-03-09",
            "2026-03-16",
        ]

    def test_rejects_too_many_weeks(self, app_runner):
        response = app_runner.get(
            URL,
            params={"first_week": dt.date.today().isoformat(), "weeks": 500},
            headers=bearer(roles=["ADMIN"]),
        )
        assert response.status_code == 422
