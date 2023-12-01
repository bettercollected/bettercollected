from dataclasses import dataclass


@dataclass
class ImportFormParams:
    workspace_id: str
    form_id: str
