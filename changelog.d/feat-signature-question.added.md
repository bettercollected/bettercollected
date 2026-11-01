- The server accepts a signature question (form spec, builder save, API, MCP, CSV): the
  respondent signs by drawing or by typing a name. A drawn signature is stored as a private
  file that the isolated document sandbox re-encodes; a typed one is stored in the encrypted
  answer. It records a name and does not check who signed. Behind a new server setting,
  `SIGNATURE_QUESTION_ENABLED` (off by default).
