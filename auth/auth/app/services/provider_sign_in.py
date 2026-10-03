"""Which account a login provider's sign-in may use (#758).

Accounts are keyed by email, so a provider sign-in reaches whatever account
holds the email the provider returns: that person's workspaces, forms and
responses. A provider may therefore use (or create) the account for an email
only when it vouches that the user owns that email:

- **OTP** proves it by construction (the code went to that inbox); it does not
  come through here.
- **Google** proves it when userinfo reports ``verified_email`` (OpenID
  Connect: ``email_verified``) true.
- **Typeform** returns an email from ``/me`` with no verification guarantee, so
  its sign-ins are always refused, for existing *and* new accounts. A new
  account under an unproven address would squat it: the real owner who later
  signs in with OTP or Google lands in an account the squatter set up, whose
  session may still be live, and the squatter can publish forms under that
  person's address meanwhile.

An unproven sign-in is refused the same way whether or not an account exists,
so the refusal tells nobody which emails have accounts. New providers (SSO)
should come through ``account_for_provider_sign_in`` with their own
``email_verified`` reading.
"""

from typing import Optional

from auth.app.repositories.user_repository import UserRepository  # noqa: F401
from auth.app.schemas.user import UserDocument

# The code the backend appends to the login page's URL (``login_error=``) so the
# webapp can explain the refusal; keep it in sync with the webapp's login view.
UNVERIFIED_EMAIL = "unverified_email"


class ProviderSignInRefused(Exception):
    """The provider did not prove the user owns the email it returned."""

    def __init__(self, provider: str, code: str = UNVERIFIED_EMAIL):
        super().__init__(f"{provider} sign-in refused: {code}")
        self.provider = provider
        self.code = code


def may_sign_in(email: Optional[str], email_verified: bool) -> bool:
    """Whether a provider sign-in may use or create the account for ``email``:
    only when the provider verified it. Deliberately independent of whether the
    account exists (see the module docstring)."""
    return bool(email and email.strip()) and email_verified is True


async def account_for_provider_sign_in(
    user_repository: "UserRepository",
    provider: str,
    email: Optional[str],
    email_verified: bool,
    **profile,
) -> UserDocument:
    """The account a ``provider`` sign-in for ``email`` signs in to, created when
    missing (``profile``: ``save_user``'s keyword arguments). Raises
    ``ProviderSignInRefused`` without touching the store when the provider did
    not verify the email."""
    if not may_sign_in(email, email_verified):
        raise ProviderSignInRefused(provider)
    return await user_repository.save_user(email, **profile)


def refused_state(state_json: dict, refusal: ProviderSignInRefused) -> dict:
    """The callback reply for a refused sign-in: the usual state (so the backend
    can send the user back to where they came from) without a user, so no
    session is issued, plus the reason for the login page."""
    state_json.pop("user", None)
    state_json["error"] = refusal.code
    state_json["provider"] = refusal.provider
    return state_json
