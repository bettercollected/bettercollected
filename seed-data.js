// Local development only. Earlier versions created a `seeduser` here; nothing
// uses it, so it is removed instead.
try {
	db.dropUser("seeduser");
} catch (error) {
	// not there
}

// Nothing else: the reference data (allowed origins, the Google Forms provider) is
// served from Postgres since 4.1. Seed it there once (docs/DEVELOPERS_GUIDE.md):
//   cd backend && uv run python -m backend.seed_refdata --origin http://localhost:3000 ...
