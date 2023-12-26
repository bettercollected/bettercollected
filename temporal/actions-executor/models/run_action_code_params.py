from dataclasses import dataclass
from typing import Optional


@dataclass
class RunActionCodeParams:
    action: str
    form: str
    response: str
    user_email: Optional[str] = None
    workspace: Optional[str] = None
