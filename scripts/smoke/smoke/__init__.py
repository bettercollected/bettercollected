"""Production smoke test of bettercollected (docs/smoke-test.md).

Runs against one dedicated test workspace with a scoped API key and a test
mailbox, both from environment variables. Reports pass/fail, timings and ids of
the test workspace only: never codes, tokens, cookies or mail contents.
"""
