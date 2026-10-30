"""Elastic APM and the privacy of a request's URL.

The APM agent records each request's full URL (and the transaction name of a
route it cannot match is the raw path), which would bring back what the
request log leaves out: the typed search in the query string and the receipt
number in a by-uuid path. Two guards, both independent of the agent's
configuration (an ``ELASTIC_APM_*`` variable cannot switch them off):

* receipt routes (``/by-uuid/``) are not traced at all;
* every transaction and error event is cleaned by :func:`redact_apm_event`
  before it is sent: no query string anywhere, receipt numbers redacted.

The processor and the client class come from ``common.utils.apm_privacy``,
shared with the auth service.
"""

from common.utils.apm_privacy import make_processor, private_client_class

from backend.app.middlewares.request_privacy import redact_receipts

#: strips the query string and receipt numbers from the request URL, the
#: transaction name and a referer header of every transaction and error event
redact_apm_event = make_processor(redact_receipts)

#: the APM client with the guards above built in
PrivateAPMClient = private_client_class(
    redact_apm_event, ignore_url=lambda url: "/by-uuid/" in url
)
