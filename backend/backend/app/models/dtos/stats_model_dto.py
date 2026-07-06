from typing import Any, Dict

from pydantic import BaseModel

_STATS_METRICS = ("pageviews", "visitors", "visits", "bounces", "totaltime")


class StatDetailModel(BaseModel):
    value: int
    prev: int


class StatsModel(BaseModel):
    pageviews: StatDetailModel
    visitors: StatDetailModel
    visits: StatDetailModel
    bounces: StatDetailModel
    totaltime: StatDetailModel

    @classmethod
    def from_umami(cls, raw: Dict[str, Any]) -> "StatsModel":
        """Build from Umami's `/stats` response shape.

        Umami returns flat current-period ints alongside a sibling
        `comparison` object holding the previous period's ints, e.g.
        `{"pageviews": 18, ..., "comparison": {"pageviews": 0, ...}}` —
        not the nested `{value, prev}` per metric the rest of the app expects.
        """
        comparison = raw.get("comparison") or {}
        return cls(
            **{
                metric: {
                    "value": raw.get(metric, 0),
                    "prev": comparison.get(metric, 0),
                }
                for metric in _STATS_METRICS
            }
        )
