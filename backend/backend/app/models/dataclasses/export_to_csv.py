from dataclasses import dataclass
from typing import List, Dict, Any


@dataclass
class ExportCSVParams:
    form: str
    responses: List[str]
    user_email: str
