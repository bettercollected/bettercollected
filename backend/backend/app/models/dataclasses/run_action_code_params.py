from dataclasses import dataclass
from typing import Any


@dataclass
class RunActionCodeParams:
    action: Any
    form: Any
    response: Any
    user_email: str
