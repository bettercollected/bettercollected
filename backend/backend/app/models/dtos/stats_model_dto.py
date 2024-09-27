from pydantic import BaseModel


class StatDetailModel(BaseModel):
    value: int
    prev: int


class StatsModel(BaseModel):
    pageviews: StatDetailModel
    visitors: StatDetailModel
    visits: StatDetailModel
    bounces: StatDetailModel
    totaltime: StatDetailModel
