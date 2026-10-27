"""A local https server with a throw-away CA, for the registration tests.

The code under test connects the way production does (resolve, pin the
address, TLS verified against the host name) except that ``resolve`` answers a
public address and the connection is dialled to this server instead. Nothing
here can be enabled by a setting: it replaces module-level functions of
``services/registration/client.py`` for the length of a test.
"""

import asyncio
import datetime as dt
import ssl
import tempfile
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Tuple

import httpcore
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

HOST = "case.example.org"
PUBLIC_ADDRESS = "93.184.216.34"


def _name(common_name: str) -> x509.Name:
    return x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])


def make_certificates(host: str = HOST) -> Tuple[bytes, bytes, bytes]:
    """``(ca_pem, server_cert_pem, server_key_pem)``."""
    now = dt.datetime.now(dt.timezone.utc)
    ca_key = ec.generate_private_key(ec.SECP256R1())
    ca = (
        x509.CertificateBuilder()
        .subject_name(_name("test ca"))
        .issuer_name(_name("test ca"))
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(minutes=5))
        .not_valid_after(now + dt.timedelta(days=1))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                key_cert_sign=True,
                crl_sign=True,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(
            x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()),
            critical=False,
        )
        .sign(ca_key, hashes.SHA256())
    )
    key = ec.generate_private_key(ec.SECP256R1())
    cert = (
        x509.CertificateBuilder()
        .subject_name(_name(host))
        .issuer_name(ca.subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(minutes=5))
        .not_valid_after(now + dt.timedelta(days=1))
        .add_extension(
            x509.SubjectAlternativeName([x509.DNSName(host)]), critical=False
        )
        .add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()),
            critical=False,
        )
        .sign(ca_key, hashes.SHA256())
    )
    return (
        ca.public_bytes(serialization.Encoding.PEM),
        cert.public_bytes(serialization.Encoding.PEM),
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ),
    )


@dataclass
class Request:
    method: str
    target: str
    headers: dict
    body: bytes


@dataclass
class Script:
    """What the server answers, in order; the last entry repeats."""

    answers: List[Tuple[int, dict, bytes]] = field(
        default_factory=lambda: [(200, {}, b"{}")]
    )
    delay: float = 0.0
    reply_body: Optional[Callable[[], bytes]] = None


class TlsServer:
    def __init__(self, host: str = HOST):
        self.host = host
        self.requests: List[Request] = []
        self.script = Script()
        self.dialled: List[Tuple[str, int]] = []
        self._server = None
        self.port = 0
        self._ca, cert, key = make_certificates(host)
        self._cert, self._key = cert, key

    async def __aenter__(self):
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        with tempfile.NamedTemporaryFile() as cert, tempfile.NamedTemporaryFile() as key:
            cert.write(self._cert)
            cert.flush()
            key.write(self._key)
            key.flush()
            context.load_cert_chain(cert.name, key.name)
        self._server = await asyncio.start_server(
            self._handle, "127.0.0.1", 0, ssl=context
        )
        self.port = self._server.sockets[0].getsockname()[1]
        return self

    async def __aexit__(self, *exc):
        self._server.close()
        await self._server.wait_closed()

    def client_context(self) -> ssl.SSLContext:
        context = ssl.create_default_context()
        context.load_verify_locations(cadata=self._ca.decode())
        return context

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        try:
            head = await reader.readuntil(b"\r\n\r\n")
            lines = head.decode("latin-1").split("\r\n")
            method, target, _version = lines[0].split(" ", 2)
            headers = {}
            for line in lines[1:]:
                if ":" in line:
                    name, value = line.split(":", 1)
                    headers[name.strip().lower()] = value.strip()
            length = int(headers.get("content-length", "0"))
            body = await reader.readexactly(length) if length else b""
            self.requests.append(Request(method, target, headers, body))
            if self.script.delay:
                await asyncio.sleep(self.script.delay)
            index = min(len(self.requests) - 1, len(self.script.answers) - 1)
            status, extra, payload = self.script.answers[index]
            if self.script.reply_body is not None:
                payload = self.script.reply_body()
            lines_out = [f"HTTP/1.1 {status} X", f"Content-Length: {len(payload)}"]
            lines_out += [f"{k}: {v}" for k, v in extra.items()]
            writer.write(("\r\n".join(lines_out) + "\r\n\r\n").encode() + payload)
            await writer.drain()
        except (asyncio.IncompleteReadError, ConnectionError, ssl.SSLError):
            pass
        finally:
            try:
                writer.close()
            except Exception:  # noqa: BLE001
                pass


class DialToServer(httpcore.AnyIOBackend):
    """Dials the local server whatever address it is told (and records it)."""

    def __init__(self, server: TlsServer):
        self._server = server

    async def connect_tcp(
        self, host, port, timeout=None, local_address=None, socket_options=None
    ):
        self._server.dialled.append((host, port))
        return await super().connect_tcp(
            "127.0.0.1",
            self._server.port,
            timeout=timeout,
            local_address=local_address,
            socket_options=socket_options,
        )
