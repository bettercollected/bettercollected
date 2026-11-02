"""The workspace rule "require an authenticator app for members" (docs/totp.md).

Applied next to the single sign-on rule on every request that reaches a
workspace (``AuthorizationService``): a member's session without a second factor
(no ``mfa`` claim) is refused with 403 ``mfa_required``, and the webapp sends the
person to set up or present the factor in that same session. Nobody is signed
out. Only while ``TOTP_ENABLED`` is on.

Not covered, on purpose, as for single sign-on: API keys and MCP (machine
credentials issued inside the workspace), and a respondent-scoped session (it
holds no workspace permission anyway). A single sign-on session that signed in
through this workspace's own identity provider counts as met: the identity
provider vouches for the person and its multi-factor policy is the customer's.
"""

from http import HTTPStatus
from typing import Optional

from backend.app.exceptions import HTTPException
from backend.app.services.mfa.service import totp_enabled
from backend.app.services.session_service import RESPONDENT_SCOPE, SSO_METHOD

API_KEY_METHOD = "api_key"
REQUIRED_CODE = "mfa_required"


def mfa_required_error() -> HTTPException:
    return HTTPException(
        HTTPStatus.FORBIDDEN,
        content={
            "code": REQUIRED_CODE,
            "message": "This workspace requires a second factor. Set up or "
            "enter the code from your authenticator app.",
        },
    )


def blocks_session(workspace, user) -> bool:
    """Whether ``user``'s session must be refused for want of a second factor.
    The caller already holds the workspace row and has checked the membership:
    nothing is read."""
    if workspace is None or not totp_enabled():
        return False
    if workspace.disabled or not getattr(workspace, "require_totp", False):
        return False
    if getattr(user, "mfa", None):
        return False
    method: Optional[str] = getattr(user, "auth_method", None)
    if method == API_KEY_METHOD:
        return False
    if getattr(user, "session_scope", None) == RESPONDENT_SCOPE:
        return False
    if (
        method == SSO_METHOD
        and getattr(user, "sso_workspace_id", None) is not None
        and str(user.sso_workspace_id) == str(workspace.id)
    ):
        return False
    return True
