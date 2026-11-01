"""``FastMail`` that connects to the address the egress rules checked.

``fastapi_mail`` hands the server's *name* to the SMTP client, which resolves it
again at connect time: a name that answers with a public address for the check
and an internal one a moment later would reach the internal one. Here the check
and the connection are one step (``egress.connect_smtp``: resolve, judge every
answer, connect to that address), and the SMTP client is given the connected
socket plus the host name, which it keeps for TLS (SNI and the certificate check),
so it never resolves anything. The message is built by ``FastMail`` itself
(templates, headers), so what is sent is unchanged.
"""

import asyncio
from typing import Optional, Sequence, Tuple

import aiosmtplib
from fastapi_mail import ConnectionConfig, FastMail

from utilities import egress
from wrappers.thread_pool_executor import thread_pool_executor

CONNECT_TIMEOUT_SECONDS = 10.0
SMTP_TIMEOUT_SECONDS = 20.0


class PinnedFastMail(FastMail):
    def __init__(self, config: ConnectionConfig) -> None:
        super().__init__(config)
        self._allow: list = []
        self._trusted = False  # strict until told otherwise

    def pin(
        self, allow: Sequence[Tuple[str, Optional[int]]] = (), trusted: bool = False
    ) -> None:
        """The egress policy of this send: the operator's allow list, and whether
        the SMTP settings are the instance's own (not judged)."""
        self._allow = list(allow)
        self._trusted = trusted

    async def send_message(
        self,
        message,
        template_name: Optional[str] = None,
        html_template: Optional[str] = None,
        plain_template: Optional[str] = None,
    ) -> None:
        prepared = await self.get_message(
            message,
            template_name=template_name,
            html_template=html_template,
            plain_template=plain_template,
        )
        messages = prepared if isinstance(prepared, list) else [prepared]
        config = self.config
        sock = await asyncio.get_running_loop().run_in_executor(
            thread_pool_executor,
            lambda: egress.connect_smtp(
                config.MAIL_SERVER,
                config.MAIL_PORT,
                allow=self._allow,
                trusted=self._trusted,
                timeout=CONNECT_TIMEOUT_SECONDS,
            ),
        )
        smtp = aiosmtplib.SMTP(
            hostname=config.MAIL_SERVER,
            sock=sock,
            use_tls=config.MAIL_SSL_TLS,
            start_tls=config.MAIL_STARTTLS,
            validate_certs=config.VALIDATE_CERTS,
            timeout=SMTP_TIMEOUT_SECONDS,
            local_hostname=config.LOCAL_HOSTNAME,
            cert_bundle=config.CERT_BUNDLE,
        )
        try:
            await smtp.connect()
            if config.USE_CREDENTIALS:
                await smtp.login(
                    config.MAIL_USERNAME, config.MAIL_PASSWORD.get_secret_value()
                )
            for item in messages:
                await smtp.send_message(item)
            await smtp.quit()
        finally:
            smtp.close()
            sock.close()
