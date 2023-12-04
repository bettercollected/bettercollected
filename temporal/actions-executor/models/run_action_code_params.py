from dataclasses import dataclass
from typing import Any


@dataclass
class RunActionCodeParams:
    action_code: str
    form: Any
    response: Any
