import pytest

from backend.app.container import container
from backend.app.services.custom_domain_service import CustomDomainService
from backend.config.custom_domain import CustomDomainSettings
from tests.app.custom_domain.fake import FakeClient

SECRET = "whsec_test"


@pytest.fixture
def fake_client():
    """Point the workspace service at an in-memory custom-domain service."""
    client = FakeClient()
    service = CustomDomainService(
        CustomDomainSettings(
            api_url="https://domains.example.net",
            api_credential="cd_test",
            application_id="app-1",
            webhook_secrets=SECRET,
        ),
        client,
    )
    workspace_service = container.workspace_service()
    previous = workspace_service.custom_domain_service
    workspace_service.custom_domain_service = service
    container.custom_domain_service.override(service)
    yield client
    workspace_service.custom_domain_service = previous
    container.custom_domain_service.reset_override()
