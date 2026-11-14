"""The proof of work before a mail is sent (purpose ``mail``): the sign-in code
(respondent and creator) and the draft link.

One line for each route: ``await require_mail_proof(request, ...)`` before the
route does anything that mails or counts. While ``CAPTCHA_ENABLED`` is off it
returns at once and the header is not even read, so the routes behave exactly as
they did. On, the request must carry a valid, unspent proof of purpose ``mail``
bound to the same workspace and form (the creator's code has no workspace, a
workspace's code no form): a proof for a response submit is refused here, and a
mail proof is refused on a submit.

The check comes first, before the per-address and per-client limits, so a request
without a proof is refused (422 with ``captcha_missing`` and the other codes of
``docs/captcha.md``) without using up anyone's budget: someone who knows an
address cannot lock its owner out of the code mail without solving a proof for
every request.
"""

from typing import Optional

from starlette.requests import Request

from backend.app.services.captcha import challenge
from backend.app.services.captcha.mode import captcha_enabled
from backend.app.utils.client_ip import limit_client_ip

PURPOSE = "mail"


async def require_mail_proof(
    request: Request,
    workspace_id: Optional[object] = None,
    form_id: Optional[object] = None,
) -> None:
    """422 unless the request carries a valid mail proof for this workspace and
    form (switch on); nothing at all while the switch is off."""
    if not captcha_enabled():
        return
    from backend.app.container import container

    await container.captcha_service().require(
        request.headers.get(challenge.HEADER),
        purpose=PURPOSE,
        workspace_id=str(workspace_id) if workspace_id else "",
        form_id=str(form_id) if form_id else "",
        client=limit_client_ip(request),
    )
