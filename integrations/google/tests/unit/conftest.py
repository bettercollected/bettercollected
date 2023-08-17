from unittest import mock

import pytest
from googleform.app import get_application


@pytest.fixture
def asgi_app():
    app = mock.Mock(spec=get_application())
    yield app
    del app
