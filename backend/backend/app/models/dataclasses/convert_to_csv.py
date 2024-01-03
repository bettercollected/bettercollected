from dataclasses import dataclass
from typing import List, Dict, Any


@dataclass
class ConvertCSVParams:
    form: str
    responses: List[str]
    # form: Dict[str, Any]
    # responses: List[Dict[str, Any]]
