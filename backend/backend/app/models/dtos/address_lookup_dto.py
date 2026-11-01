from fastapi_camelcase import CamelModel
from pydantic import ConfigDict, Field


class AddressLookupRequest(CamelModel):
    """What a respondent's form sends to fill in street and city: the
    question and the two values the lookup needs. Nothing else is accepted
    (the house number addition is never sent)."""

    model_config = ConfigDict(extra="forbid")

    field_id: str = Field(min_length=1, max_length=64)
    postcode: str = Field(min_length=1, max_length=12)
    house_number: str = Field(min_length=1, max_length=10)
