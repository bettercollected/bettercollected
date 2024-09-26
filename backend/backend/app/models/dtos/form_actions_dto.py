from pydantic import BaseModel


class FormActionsDto(BaseModel):
    name: str
    value: str
    type: str
