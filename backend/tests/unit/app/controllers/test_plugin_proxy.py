from http import HTTPStatus

import pytest
from fastapi.testclient import TestClient
from bettercollected_backend_server.app import get_application
from common.constants.plugin_routes import (
    PLUGIN_ROUTE_AUTHORIZE,
    PLUGIN_ROUTE_CALLBACK,
    PLUGIN_ROUTE_GET_FORM,
    PLUGIN_ROUTE_IMPORT_FORM,
    PLUGIN_ROUTE_LIST_FORMS,
    PLUGIN_ROUTE_REVOKE,
)


class TestPlugin_proxyController:
    @pytest.fixture
    def client(self):
        # This is an example fixture for generated test sake.
        # By default there should be a 'app_runner' fixture just like this under:
        # tests/unit/app/conftest.py
        app = get_application()
        with TestClient(app) as client:
            yield client

    def test_shouldauthorize_return_ok(self, client):
        # given / when
        response = client.get(PLUGIN_ROUTE_AUTHORIZE)

        # then
        assert response.status_code == HTTPStatus.OK
        assert response.json() == {"hello": "world"}

    def test_shouldcallback_return_ok(self, client):
        # given / when
        response = client.get(PLUGIN_ROUTE_CALLBACK)

        # then
        assert response.status_code == HTTPStatus.OK
        assert response.json() == {"hello": "world"}

    def test_shouldrevoke_return_ok(self, client):
        # given / when
        response = client.post(PLUGIN_ROUTE_REVOKE)

        # then
        assert response.status_code == HTTPStatus.ACCEPTED
        assert response.json() == {"hello": "world"}

    def test_shouldlist_forms_return_ok(self, client):
        # given / when
        response = client.get(PLUGIN_ROUTE_LIST_FORMS)

        # then
        assert response.status_code == HTTPStatus.OK
        assert response.json() == {"hello": "world"}

    def test_shouldget_form_return_ok(self, client):
        # given / when
        response = client.get(PLUGIN_ROUTE_GET_FORM)

        # then
        assert response.status_code == HTTPStatus.OK
        assert response.json() == {"hello": "world"}

    def test_shouldimport_form_return_ok(self, client):
        # given / when
        response = client.post(PLUGIN_ROUTE_IMPORT_FORM)

        # then
        assert response.status_code == HTTPStatus.CREATED
        assert response.json() == {"hello": "world"}
