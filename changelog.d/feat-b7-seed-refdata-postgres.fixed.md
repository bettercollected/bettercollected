- A new stack deployed with `deploy.sh` gets its reference data in Postgres, where the API reads it:
  the allowed origins (CORS and the post-sign-in redirect) and the Google Forms provider are seeded
  once by `python -m backend.seed_refdata`, after the migrations and before the services start.
  Until now a new stack had no allowed origins. The origins are the web app's public addresses
  (`HTTP_SCHEME` with `DASHBOARD_DOMAIN` / `FORM_DOMAIN`); a stack without them is taken for a
  local one and gets the localhost ports. An upgraded stack is never seeded: it imports its
  reference data from Mongo.
