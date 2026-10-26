- The actions executor starts again with `JOBS_BACKEND=postgres` (the default from 4.1). It crashed at start with
  `ImportError: no pq wrapper available`: its slim image has no libpq, so the Postgres queue driver
  (`psycopg`) now ships its bundled copy (`psycopg[binary]`).
