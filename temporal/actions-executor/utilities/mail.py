from datetime import datetime, timezone
from typing import Any, Dict, List


def response_mail_context(
    fields: List[Dict[str, Any]], creator_mail: bool, title: str, description: str
) -> Dict[str, Any]:
    """Values for templates/response-mail.html; the footer's copyright year is
    the year the mail is sent."""
    return {
        "form": fields,
        "creator_mail": creator_mail,
        "title": title,
        "description": description,
        "year": datetime.now(timezone.utc).year,
    }
