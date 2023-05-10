from typing import Optional

from pydantic import BaseModel


class FormResponseFilterQuery(BaseModel):
    dataOwnerIdentifier: Optional[str] = None
