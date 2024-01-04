from http import HTTPStatus
from typing import Any

from aiohttp import ClientResponse
from common.constants import MESSAGE_NOT_FOUND, MESSAGE_OAUTH_MISSING_REFRESH_TOKEN, \
    MESSAGE_OAUTH_MISSING_TOKEN_OR_EXPIRY, MESSAGE_OAUTH_INVALID_GRANT
from common.enums.form_provider import FormProvider
from googleapiclient.errors import HttpError
from oauthlib.oauth2 import InvalidGrantError

from googleform.app.exceptions.http import HTTPException
from googleform.app.repositories.oauth_credential import OauthCredentialRepository
from googleform.app.schemas.oauth_credential import Oauth2CredentialDocument
from googleform.app.services.oauth_google import OauthGoogleService
from googleform.app.utils import AiohttpClient
from googleform.config import settings


class OauthCredentialService:
    """
    Class for interacting with OAuth2 credential documents.

    This class provides a convenient way to access OAuth2 credential
    documents and perform various operations on them.
    """

    def __init__(
        self,
        oauth_credential_repo: OauthCredentialRepository,
        oauth_google_service: OauthGoogleService,
    ):
        """Initialize the OAuth2 credential service.

        Args:
            oauth_credential_repo (OauthCredentialRepository): An instance
                of the OAuth2 credential repository.
            oauth_google_service (OauthGoogleService): An instance of the
                OAuth2 Google service.
        """

        self.oauth_credential_repo: OauthCredentialRepository = oauth_credential_repo
        self.oauth_google_service: OauthGoogleService = oauth_google_service

    async def _get_oauth_credential(
        self, email: str, provider: FormProvider = FormProvider.GOOGLE
    ) -> Oauth2CredentialDocument:
        """
        Get an OAuth2 credential document by email and provider.

        Args:
            email (str): The email of the user to get the credential for.
            provider (FormProvider, optional): The provider of the form.
                Defaults to FormProvider.GOOGLE.

        Returns:
            Oauth2CredentialDocument: An OAuth2 credential document.

        Raises:
            HTTPException: If the document is not found.
        """
        return await self.oauth_credential_repo.get(email, provider)

    async def add_oauth_credential(
        self, email: str, credentials: Any, provider: FormProvider = FormProvider.GOOGLE
    ):
        """
        Add an OAuth2 credential document by email and provider.

        Args:
            email (str): The email of the user to get the credential for.
            credentials (Any): Credential object returned from OAuth authorization.
            provider (FormProvider, optional): The provider of the form.
                Defaults to FormProvider.GOOGLE.

        Returns:
            Oauth2CredentialDocument: An OAuth2 credential document.

        Raises:
            HTTPException: If the document is not found.
        """
        return await self.oauth_credential_repo.add(email, credentials, provider)

    async def verify_oauth_token(
        self, email: str, provider: FormProvider = FormProvider.GOOGLE
    ) -> Oauth2CredentialDocument:
        """
        Verify an OAuth2 token.

        This method retrieves an OAuth2 credential document by
        email and provider, and verifies that it has a valid refresh
        token. If the token is valid, it will be refreshed if necessary.

        Args:
            email (str): The email of the user to verify the token for.
            provider (FormProvider, optional): The provider of the form.
                Defaults to FormProvider.GOOGLE.

        Returns:
            Oauth2CredentialDocument: An OAuth2 credential document with
                a valid access token.

        Raises:
            HTTPException: If the document is not found or does not have
                a valid refresh token.
        """
        oauth_credential = await self._get_oauth_credential(email, provider)
        if not oauth_credential:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND, content=MESSAGE_NOT_FOUND
            )
        if (
            not oauth_credential.credentials
            or not oauth_credential.credentials.refresh_token
        ):
            raise HTTPException(
                status_code=HTTPStatus.UNAUTHORIZED,
                content=MESSAGE_OAUTH_MISSING_REFRESH_TOKEN,
            )
        return await self.oauth_google_service.fetch_oauth_token(oauth_credential)

    async def verify_token_validity(self, credential: Oauth2CredentialDocument):
        try:
            credential = await self.refresh_access_token(oauth_credentials=credential)
            url = f"https://www.googleapis.com/oauth2/v3/tokeninfo?access_token={credential.credentials.token}"
            verification_response: ClientResponse = await AiohttpClient.get(url)
            response = await verification_response.json()
            if not all(scope in response.get("scope") for scope in settings.GOOGLE_SCOPES.split()):
                raise HTTPException(status_code=HTTPStatus.FORBIDDEN, content="Add scopes are not authorized")
            return credential.credentials.token
        except HttpError:
            raise HTTPException(
                status_code=HTTPStatus.UNAUTHORIZED,
                content=MESSAGE_OAUTH_MISSING_TOKEN_OR_EXPIRY,
            )
        except InvalidGrantError:
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN, content=MESSAGE_OAUTH_INVALID_GRANT
            )

    async def refresh_access_token(self, oauth_credentials: Oauth2CredentialDocument):
        return await self.oauth_google_service.refresh_access_token(oauth_credential=oauth_credentials)
