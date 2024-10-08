from pydantic import BaseModel


class IntegrationCallBackDto(BaseModel):
    state: str
    code: str
    form_id: str
    action_id: str
