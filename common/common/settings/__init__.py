"""A signed, encrypted settings core: registry, canonical signing, section
keys, snapshot verification and value resolution.

Pure library: no database, HTTP, FastAPI or SQLAlchemy, and it never imports
``common.services.crypto_service`` or anything from ``backend``. Only
``cryptography`` and pydantic are used, so any service can import it.
"""
