from pydantic import BaseModel


class PriceIdRequest(BaseModel):
    price_id: str


class CreateFormWithAI(BaseModel):
    prompt: str
