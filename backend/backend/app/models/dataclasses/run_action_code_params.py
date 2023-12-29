from dataclasses import dataclass
from typing import Any, Optional, List

from common.models.standard_form import ParameterValue
from pydantic import BaseModel


class WorkspaceParameters(BaseModel):
    parameters: Optional[List[ParameterValue]]
    secrets: Optional[List[ParameterValue]]


@dataclass
class RunActionCodeParams:
    action: Any
    form: Any
    response: Any
    user_email: Optional[str] = None
    workspace: Optional[Any] = None
