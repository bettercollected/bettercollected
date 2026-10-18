"""Internal admin service: its own database schema, keys and audit log.

Isolation rule: nothing under ``backend.admin`` may import the public API's
router, container or controllers, nor ``common.services.crypto_service`` (which
refuses to import without the response-encryption keyset). The tests in
``tests/admin/test_import_isolation.py`` enforce it.
"""
