"""Test defaults: no test reaches the network. Names resolve to a public
documentation address (so the egress rules have an address to judge), and the
tests of ``utilities/egress.py`` set their own answers."""

import pytest

from utilities import egress

PUBLIC_ADDRESS = "93.184.216.34"


@pytest.fixture(autouse=True)
def names_resolve_to_a_public_address(monkeypatch):
    monkeypatch.setattr(egress, "resolve", lambda host, port: [PUBLIC_ADDRESS])
