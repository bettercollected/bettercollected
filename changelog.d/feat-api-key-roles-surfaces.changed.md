- The MCP server now rate limits API keys like the public API does: 120 tool calls a minute per
  key and 600 a minute for all of a workspace's keys together (`API_PUBLIC_API_REQUESTS_PER_WINDOW`,
  `API_PUBLIC_API_WORKSPACE_REQUESTS_PER_WINDOW`, `API_PUBLIC_API_WINDOW_SECONDS`; 0 turns a limit off),
  in budgets of their own so a burst on one surface never uses up the other's. A call over the
  limit is refused with the number of seconds to wait. Before this, a key could call MCP tools
  as fast as the database allowed, for example to page through a workspace's answers. An agent
  that made more than 120 tool calls a minute with one key now has to slow down or have the
  ceiling raised.
