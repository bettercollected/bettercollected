from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class RunActionCodeParams:
    action: str
    form: str
    response: str
    user_email: str
    parameters: Optional[Dict[str, str]]
    secrets: Optional[Dict[str, str]]
