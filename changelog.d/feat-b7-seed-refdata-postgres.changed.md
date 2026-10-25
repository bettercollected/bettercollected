- The `mongo-seed` job (deployment and local compose) no longer writes the allowed origins or the
  Google Forms provider to Mongo; it only removes the old `seeduser` account. Collections an earlier
  release seeded are left for the import. Local development seeds Postgres instead
  (docs/DEVELOPERS_GUIDE.md).
- `python -m backend.seed_refdata` refuses an `--origin` that is not an origin
  (`http(s)://host[:port]`) and stores it the way browsers send it. Without `--origin` it seeds the
  localhost ports only while `API_CLIENT_URL` is a local address, else that URL's origin.
