- The backend keeps its AI data in Postgres only: AI preference memories, AI chat sessions and
  insights, workspace AI profiles, the MCP audit log, AI form prompts and the public API's
  `Idempotency-Key` records. A `DB_READ_SOURCE__ai` or `DB_WRITE_MODE__ai` setting other than
  `postgres` now stops the backend from starting and names the setting: remove it.
