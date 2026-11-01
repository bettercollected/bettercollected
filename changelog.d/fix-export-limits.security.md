- Reads of responses through workspace API keys (the REST API and the MCP server) now
  leave an entry in the export audit log, like an export does: the key's id, the form and
  the number of responses returned, never an answer. A read that cannot be recorded fails
  instead of going unrecorded.
