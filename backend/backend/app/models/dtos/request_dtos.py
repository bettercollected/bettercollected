from pydantic import BaseModel


class PriceIdRequest(BaseModel):
    price_id: str
