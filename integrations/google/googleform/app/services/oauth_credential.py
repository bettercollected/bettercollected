from http import HTTPStatus
from typing import Any

from fastapi import HTTPException

from common.constants import MESSAGE_NOT_FOUND, MESSAGE_OAUTH_MISSING_REFRESH_TOKEN
from common.enums.form_provider import FormProvider
from googleform.app.repositories.oauth_credential import OauthCredentialRepository
from googleform.app.schemas.oauth_credential import Oauth2CredentialDocument
from googleform.app.services.oauth_google import OauthGoogleService


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
                status_code=HTTPStatus.NOT_FOUND, detail=MESSAGE_NOT_FOUND
            )
        if (
            not oauth_credential.credentials
            or not oauth_credential.credentials.refresh_token
        ):
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail=MESSAGE_OAUTH_MISSING_REFRESH_TOKEN,
            )
        return await self.oauth_google_service.fetch_oauth_token(oauth_credential)
