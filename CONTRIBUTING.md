# Contributing to bettercollected

First off — thank you for taking the time to contribute! 🎉

bettercollected is a privacy-friendly form builder made up of several services
(a Next.js frontend, FastAPI backend/auth/integration services, and Temporal
workers). This guide covers how to get set up and how to get your change merged.

- **Architecture overview:** [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- **Detailed local setup:** [docs/DEVELOPERS_GUIDE.md](docs/DEVELOPERS_GUIDE.md)
- **Per-service notes:** the `AGENTS.md` file nearest the code you're editing
  (root, `backend/`, `webapp/`, `auth/`, `temporal/`)
- **Code of Conduct:** [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)
- **Security issues:** please follow [SECURITY.md](SECURITY.md) — do **not** open
  a public issue.

## Ways to contribute

- Report bugs and request features via [GitHub Issues](../../issues) (templates
  are provided).
- Improve documentation.
- Pick up an issue labelled **`good first issue`** or **`help wanted`**.
- Fix a bug or build a feature and open a pull request.

If you're planning a large change, please open an issue to discuss it first so we
can agree on the approach before you invest a lot of time.

## Prerequisites

| Tool | Version | Notes |
|---|---|---|
| [uv](https://docs.astral.sh/uv/) | latest | Python dependency & environment manager (replaces Poetry) |
| Python | 3.11+ | uv will fetch a compatible interpreter; see [`.python-version`](.python-version) |
| Node.js | 20+ | see [`.nvmrc`](.nvmrc) |
| Yarn | 1.x (Classic) | `corepack enable` or `npm i -g yarn` |
| Docker + Docker Compose | latest | for MongoDB, nginx, and Mailpit |

## Local development

The full walkthrough (env vars, shared secrets, per-service ports, gotchas) is in
[docs/DEVELOPERS_GUIDE.md](docs/DEVELOPERS_GUIDE.md). The short version:

```bash
# 1. Start infra (MongoDB + seed data, nginx, Mailpit email inbox)
docker compose -f docker-compose.local.yml up --build -d

# 2. Configure env for each service (fill in the copied .env files)
cp backend/.env.example backend/.env
cp auth/.env.example auth/.env
cp webapp/.env.example webapp/.env
# ...and integrations/google, temporal/* as needed

# 3. Install deps
#    Python services (backend, auth, integrations/google, temporal/*):
(cd backend && uv sync)
#    Frontend:
(cd webapp && yarn install)

# 4. Run a service
(cd backend && uv run python -m uvicorn backend.app:get_application --port 8000 --reload)
(cd webapp && yarn dev)      # http://localhost:3000
```

**Important:** the auth/JWT/crypto secrets (`AUTH_JWT_SECRET`, `AUTH_AES_HEX_KEY`,
`MASTER_ENCRYPTION_KEYSET`) must be identical across `backend`, `auth`, and the
integrations, or sessions and encrypted data won't work across services. See the
developers guide for how to generate them.

## Coding standards

**Python** — formatted with `black` and linted with `flake8`:

```bash
cd backend            # or auth, integrations/google
uv run black .
uv run flake8 .
uv run pytest         # run the tests
```

**Frontend** — ESLint + Prettier, TypeScript:

```bash
cd webapp
yarn lint
yarn format:check
yarn build            # type-checks and builds
```

Please install the pre-commit hooks where a config exists
(`pre-commit install`) so formatting/lint issues are caught before you commit.
Commit from the terminal so hook failures are visible.

## Pull request process

1. **Branch off `develop`** (the default branch). Use a descriptive name, e.g.
   `fix/forms-listing-pagination` or `feat/webhook-retries`.
2. Keep PRs focused and reasonably small. One logical change per PR.
3. Make sure the app still works — run the relevant tests (`uv run pytest` for
   Python services, `yarn test:run` for the webapp), and for frontend changes
   confirm `yarn build` passes.
4. Update docs (`README`, `docs/`, the relevant `AGENTS.md`) when behavior or
   setup changes.
5. Fill in the PR template, link the issue it closes, and describe how you
   tested the change.
6. Ensure CI is green. A maintainer will review; please respond to feedback.
7. **Never commit secrets.** `.env.example` files must contain placeholders only.

### Commit messages

Write clear, imperative commit messages (e.g. "Fix null value on responder
input"). Conventional Commit prefixes (`feat:`, `fix:`, `docs:`, `chore:`,
`refactor:`, `test:`) are encouraged and help us generate release notes — see
[RELEASING.md](RELEASING.md) for the conventions and release process.

For user-facing changes, add a line under `## [Unreleased]` in
[CHANGELOG.md](CHANGELOG.md) as part of your PR.

## License

By contributing, you agree that your contributions will be licensed under the
[Apache License 2.0](LICENSE) that covers this project.
