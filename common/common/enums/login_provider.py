import enum


class LoginProvider(str, enum.Enum):
    """The OAuth providers a user can sign in with (``/auth/{provider}/basic``).

    Google only. Typeform sign-in was always refused (its email is not
    verified) and was removed with the rest of the Typeform integration.
    """

    GOOGLE = "google"
