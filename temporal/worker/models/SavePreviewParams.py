from dataclasses import dataclass


@dataclass
class SavePreviewParams:
    template_url: str
    template_id: str
    token: str
