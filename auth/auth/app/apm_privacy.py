"""Elastic APM for the auth service: what a request carries stays out.

The backend calls this service with emails and sign-in codes in the query
string (``/auth/otp/validate``, ``/auth/otp/send``), the shared internal key in
a header, and assertions and Stripe payloads in bodies; the code is a local
variable while it is mailed or checked. Every transaction, span and error
event is cleaned before it is sent (``common.utils.apm_privacy``, strict): no
query string in a URL or name, no request headers, cookies or body, no local
variables in a stack frame (never collected either), no database parameters in
an error message. The client always loads the processor; no ``ELASTIC_APM_*``
setting switches it off.
"""

from common.utils.apm_privacy import make_processor, private_client_class

redact_apm_event = make_processor(strict=True)

PrivateAPMClient = private_client_class(redact_apm_event, strict=True)
