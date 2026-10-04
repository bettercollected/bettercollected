"""Smoke check against real DNS. Skipped unless BC_LIVE_DNS_TESTS=1, so the
suite never depends on the network:

    BC_LIVE_DNS_TESTS=1 uv run pytest tests/app/services/test_domain_dns_live.py
"""

import os
import secrets

import pytest

from backend.app.services.domains import dns_txt

pytestmark = pytest.mark.skipif(
    os.environ.get("BC_LIVE_DNS_TESTS") != "1",
    reason="real DNS lookups; set BC_LIVE_DNS_TESTS=1 to run",
)


async def test_a_domain_we_do_not_control_fails_cleanly():
    resolver = dns_txt.make_resolver(5.0)
    result = await dns_txt.check_token(resolver, "example.com", secrets.token_hex(16))
    assert result == dns_txt.CheckResult(False, dns_txt.NO_RECORD)


async def test_a_name_with_txt_records_is_read_but_does_not_match():
    # _dmarc.<domain> is a public TXT record most large domains publish
    resolver = dns_txt.make_resolver(5.0)
    values = await dns_txt.lookup_txt(resolver, "_dmarc.gmail.com")
    assert any(value.startswith("v=DMARC1") for value in values)
