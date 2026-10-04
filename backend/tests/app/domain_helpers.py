"""A stand-in for DNS: tests never resolve real names.

``FakeDNS`` replaces dnspython's async resolver ``resolve``: each name maps to
a list of TXT values or to an exception to raise; unknown names are NXDOMAIN.
"""

from types import SimpleNamespace
from typing import Dict, List, Union

import dns.asyncresolver
import dns.resolver
import pytest


class FakeDNS:
    def __init__(self):
        self.records: Dict[str, Union[List[str], BaseException]] = {}
        self.queries: List[tuple] = []

    def set_txt(self, name: str, *values: str) -> None:
        self.records[name] = list(values)

    def fail(self, name: str, error: BaseException) -> None:
        self.records[name] = error

    def clear(self, name: str) -> None:
        self.records.pop(name, None)

    async def resolve(self, resolver, qname, rdtype="A", *args, **kwargs):
        name = str(qname).rstrip(".")
        self.queries.append((name, rdtype, kwargs.get("search")))
        entry = self.records.get(name)
        if entry is None:
            raise dns.resolver.NXDOMAIN()
        if isinstance(entry, BaseException):
            raise entry
        if not entry:
            return SimpleNamespace(rrset=None)
        rdatas = [
            # a long value arrives split into 255-byte character-strings
            SimpleNamespace(
                strings=[
                    value.encode()[i : i + 255]
                    for i in range(0, max(len(value.encode()), 1), 255)
                ]
            )
            for value in entry
        ]
        return SimpleNamespace(rrset=rdatas)


@pytest.fixture
def fake_dns(monkeypatch):
    fake = FakeDNS()

    async def resolve(self, qname, rdtype="A", *args, **kwargs):
        return await fake.resolve(self, qname, rdtype, *args, **kwargs)

    monkeypatch.setattr(dns.asyncresolver.Resolver, "resolve", resolve)
    return fake
