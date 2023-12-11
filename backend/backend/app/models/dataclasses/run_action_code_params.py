from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class RunActionCodeParams:
    action: Any
    form: Any
    response: Any
    user_email: str
    parameters: Optional[Dict[str, str]] = None
    secrets: Optional[Dict[str, str]] = None
