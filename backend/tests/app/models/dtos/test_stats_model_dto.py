from backend.app.models.dtos.stats_model_dto import StatsModel


def test_from_umami_reshapes_flat_response_with_comparison():
    raw = {
        "pageviews": 18,
        "visitors": 2,
        "visits": 2,
        "bounces": 1,
        "totaltime": 1432,
        "comparison": {
            "pageviews": 5,
            "visitors": 1,
            "visits": 1,
            "bounces": 0,
            "totaltime": 100,
        },
    }

    stats = StatsModel.from_umami(raw)

    assert stats.pageviews.value == 18
    assert stats.pageviews.prev == 5
    assert stats.totaltime.value == 1432
    assert stats.totaltime.prev == 100


def test_from_umami_defaults_missing_fields_to_zero():
    stats = StatsModel.from_umami({"pageviews": 3})

    assert stats.pageviews.value == 3
    assert stats.pageviews.prev == 0
    assert stats.visitors.value == 0
    assert stats.visitors.prev == 0
