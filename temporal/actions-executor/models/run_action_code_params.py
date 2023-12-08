from dataclasses import dataclass
from typing import Dict, Optional, List


@dataclass
class RunActionCodeParams:
    action: str
    form: str
    response: str
    user_email: str
    parameters: Optional[List[Dict[str, str]]]
    secrets: Optional[List[Dict[str, str]]]
