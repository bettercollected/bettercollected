import pytest

from common.services.crypto_service import CryptoService


@pytest.fixture
def test_keyset():
    keyset = (
        "ewogICAgICAgICAgImtleSI6IFt7CiAgICAgICAgICAgICAgImtleURhdGEiOiB7CiAgICAgICAgI"
        "CAgICAgICAgICJrZXlNYXRlcmlhbFR5cGUiOgogICAgICAgICAgICAgICAgICAgICAgIlNZTU1FVF"
        "JJQyIsCiAgICAgICAgICAgICAgICAgICJ0eXBlVXJsIjoKICAgICAgICAgICAgICAgICAgICAgICJ"
        "0eXBlLmdvb2dsZWFwaXMuY29tL2dvb2dsZS5jcnlwdG8udGluay5BZXNHY21LZXkiLAogICAgICAg"
        "ICAgICAgICAgICAidmFsdWUiOgogICAgICAgICAgICAgICAgICAgICAgIkdpQld5VWZHZ1lrM1JUU"
        "mhqL0xJVXpTdWRJV2x5akNmdENPeXBUcjBqQ05TTGc9PSIKICAgICAgICAgICAgICB9LAogICAgIC"
        "AgICAgICAgICJrZXlJZCI6IDI5NDQwNjUwNCwKICAgICAgICAgICAgICAib3V0cHV0UHJlZml4VHl"
        "wZSI6ICJUSU5LIiwKICAgICAgICAgICAgICAic3RhdHVzIjogIkVOQUJMRUQiCiAgICAgICAgICB9"
        "XSwKICAgICAgICAgICJwcmltYXJ5S2V5SWQiOiAyOTQ0MDY1MDQKICAgICAgfQ=="
    )
    return keyset


@pytest.fixture
def crypto_service(test_keyset):
    return CryptoService(test_keyset)


def test_encryption_decryption(crypto_service):
    workspace_id = "my-workspace-id-1" * 100
    form_id = "my-form-id-1" * 100
    response_data = "some-json-string" * 1000

    encrypted_response = crypto_service.encrypt(workspace_id, form_id, response_data)
    decrypted_response = crypto_service.decrypt(
        workspace_id, form_id, encrypted_response
    )

    assert isinstance(decrypted_response, bytes)
    assert bytes(response_data, "utf-8") == decrypted_response
