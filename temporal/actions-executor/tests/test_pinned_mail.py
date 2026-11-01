"""The mail connection goes to the address the egress rules checked, and the SMTP
client is never left to resolve the name again (utilities/pinned_mail.py)."""

import asyncio
import socket

import pytest
from fastapi_mail import ConnectionConfig, MessageSchema, MessageType

from utilities import egress
from utilities.pinned_mail import PinnedFastMail


class FakeSMTP:
    """A minimal SMTP server: records who connected and what it was sent."""

    def __init__(self):
        self.peers = []
        self.messages = []
        self.server = None
        self.port = None

    async def start(self):
        self.server = await asyncio.start_server(self.handle, "127.0.0.1", 0)
        self.port = self.server.sockets[0].getsockname()[1]

    async def handle(self, reader, writer):
        self.peers.append(writer.get_extra_info("peername")[0])
        writer.write(b"220 fake ESMTP\r\n")
        data = b""
        in_data = False
        while True:
            line = await reader.readline()
            if not line:
                break
            if in_data:
                data += line
                if line == b".\r\n":
                    in_data = False
                    self.messages.append(data)
                    writer.write(b"250 queued\r\n")
                continue
            command = line.split(b" ")[0].strip().upper()
            if command == b"EHLO":
                writer.write(b"250-fake\r\n250 8BITMIME\r\n")
            elif command == b"DATA":
                in_data = True
                writer.write(b"354 go\r\n")
            elif command == b"QUIT":
                writer.write(b"221 bye\r\n")
                await writer.drain()
                break
            else:
                writer.write(b"250 ok\r\n")
            await writer.drain()
        writer.close()

    async def stop(self):
        self.server.close()
        await self.server.wait_closed()


def config(port):
    return ConnectionConfig(
        MAIL_USERNAME="u",
        MAIL_PASSWORD="p",
        MAIL_FROM="forms@acme.example",
        MAIL_PORT=port,
        MAIL_SERVER="mail.acme.example",
        MAIL_STARTTLS=False,
        MAIL_SSL_TLS=False,
        USE_CREDENTIALS=False,
        VALIDATE_CERTS=False,
        TEMPLATE_FOLDER="templates",
    )


def message():
    return MessageSchema(
        subject="Hello",
        recipients=["owner@acme.example"],
        body="<p>the body</p>",
        subtype=MessageType.html,
    )


def test_the_connection_goes_to_the_checked_address_and_the_client_never_resolves(
    monkeypatch,
):
    resolved = []
    lookups = []

    def resolve(host, port):
        resolved.append(host)
        return ["127.0.0.1"]

    real = socket.getaddrinfo

    def counting(*args, **kwargs):
        lookups.append(args[0])
        return real(*args, **kwargs)

    monkeypatch.setattr(egress, "resolve", resolve)
    monkeypatch.setattr(socket, "getaddrinfo", counting)

    async def go():
        server = FakeSMTP()
        await server.start()
        try:
            mailer = PinnedFastMail(config(server.port))
            mailer.pin(allow=[("mail.acme.example", server.port)])
            await mailer.send_message(message())
        finally:
            await server.stop()
        return server

    server = asyncio.run(go())
    assert server.peers == ["127.0.0.1"]
    import email

    received = email.message_from_bytes(server.messages[0].rstrip(b".\r\n") + b"\r\n")
    assert received["Subject"] == "Hello"
    bodies = [
        part.get_payload(decode=True)
        for part in received.walk()
        if not part.is_multipart()
    ]
    assert b"<p>the body</p>" in bodies
    # the name was resolved once, by the egress rules; nothing else looked it up
    assert resolved == ["mail.acme.example"]
    assert "mail.acme.example" not in lookups


def test_an_internal_answer_is_refused_before_any_connection(monkeypatch):
    monkeypatch.setattr(egress, "resolve", lambda host, port: ["10.0.0.5"])

    def no_connection(*args, **kwargs):
        raise AssertionError("a connection was attempted")

    monkeypatch.setattr(egress.socket, "create_connection", no_connection)

    async def go():
        mailer = PinnedFastMail(config(587))
        await mailer.send_message(message())

    with pytest.raises(egress.EgressRefused) as refused:
        asyncio.run(go())
    assert refused.value.code == "not_allowed"


def test_the_instances_own_server_is_connected_to_without_being_judged(monkeypatch):
    monkeypatch.setattr(egress, "resolve", lambda host, port: ["127.0.0.1"])

    async def go():
        server = FakeSMTP()
        await server.start()
        try:
            mailer = PinnedFastMail(config(server.port))
            mailer.pin(trusted=True)  # port is not a submission port: not judged
            await mailer.send_message(message())
        finally:
            await server.stop()
        return server

    assert asyncio.run(go()).peers == ["127.0.0.1"]


def test_a_name_that_changes_its_answer_after_the_check_reaches_nothing_else(
    monkeypatch,
):
    answers = iter([["127.0.0.1"], ["10.0.0.5"]])
    monkeypatch.setattr(egress, "resolve", lambda host, port: next(answers))

    async def go():
        server = FakeSMTP()
        await server.start()
        try:
            mailer = PinnedFastMail(config(server.port))
            mailer.pin(allow=[("mail.acme.example", server.port)])
            await mailer.send_message(message())  # the one resolution: 127.0.0.1
        finally:
            await server.stop()
        return server

    # the second answer (internal) is never asked for: one resolution per send
    server = asyncio.run(go())
    assert server.peers == ["127.0.0.1"]
