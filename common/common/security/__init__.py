"""Security primitives shared by the services: a time source, RFC 6238 TOTP and
the shape of one-time recovery codes. Pure functions on the standard library;
storage, keys and rate limits stay with each service."""
