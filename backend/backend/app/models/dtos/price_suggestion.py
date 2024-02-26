from pydantic import BaseModel


class PriceSuggestionRequest(BaseModel):
    price: int
