from dataclasses import dataclass


@dataclass
class RunActionCodeParams:
    action: str
    form: str
    response: str
    user_email: str
