"""Elastic APM for the auth service: nothing a request carries beyond its
method and path.

The backend calls this service with emails and sign-in codes in the query
string (``/auth/otp/validate``), the shared internal key in a header, and
assertions and Stripe payloads in bodies. Every transaction and error event is
cleaned before it is sent (``common.utils.apm_privacy``, strict): no query
string in the URL or the transaction name, no request headers, cookies or
body, no local variables in a stack frame. The client always loads the
processor; no ``ELASTIC_APM_*`` setting switches it off.
"""

from common.utils.apm_privacy import make_processor, private_client_class

redact_apm_event = make_processor(strict=True)

PrivateAPMClient = private_client_class(redact_apm_event)
