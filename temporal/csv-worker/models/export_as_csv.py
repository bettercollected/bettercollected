from dataclasses import dataclass
from typing import List


@dataclass
class ExportCSVParams:
    form: str
    responses: List[str]
    user_email: str

