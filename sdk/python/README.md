# BetterCollected Python SDK and CLI

A small typed client for the
[BetterCollected public API](https://github.com/bettercollected/bettercollected/blob/develop/docs/api/README.md)
(`httpx` and Pydantic), and the `bettercollected` command line tool for
keeping forms as code. The models are generated from the form spec JSON
Schema and the API's OpenAPI document.

Works with bettercollected 4.1 or later, on bettercollected.com or on your
own instance. Python 3.10 or later.

- Documentation: https://bettercollected.com/developers/
- Source: https://github.com/bettercollected/bettercollected/tree/develop/sdk/python
- Issues: https://github.com/bettercollected/bettercollected/issues

## Install

```bash
pip install bettercollected
```

or `uv add bettercollected`. This installs the library and the
`bettercollected` command.

## API key

A workspace admin creates an API key on the dashboard's **AI → MCP** tab
(`/<workspace>/dashboard/ai/mcp`). A key works in its own workspace only and
never does more than the person who created it may do. Keep it out of your
code and pass it in through the environment.

## Quick start

```python
import os
from bettercollected import BetterCollected, BetterCollectedError

with BetterCollected(os.environ["BETTERCOLLECTED_API_KEY"], "https://forms.example.org") as bc:
    created = bc.create_form({"specVersion": "1", "title": "Sign-up", "pages": [{"id": "p1", "fields": []}]}, idempotency_key="signup-v1")
    ops = [{"op": "add_field", "pageId": "p1", "field": {"title": "Your email", "type": "email", "required": True}}]
    result = bc.apply_ops(created.form_id, ops, if_match=created.etag)
    try:
        bc.publish_form(created.form_id)
    except BetterCollectedError as error:
        print(error.code, [(e.path, e.message) for e in error.errors])
```

The second argument is the address of your instance. Reads that return a
version give `Versioned(value, etag)`; pass the `etag` as `if_match` to
change exactly that version.

## Forms as code (CLI)

JSON is the canonical format; YAML (`.yaml`, `.yml`) works too. The API key
is read from `BETTERCOLLECTED_API_KEY` only; the instance from `--url` or
`BETTERCOLLECTED_URL`.

```bash
export BETTERCOLLECTED_URL=https://forms.example.org
export BETTERCOLLECTED_API_KEY=bc_...

bettercollected pull 6123abc... -o signup.json   # write the form to a file
bettercollected validate signup.json             # check it (exit 1 when invalid)
bettercollected diff signup.json                 # what push would change
bettercollected push signup.json                 # replace the form
bettercollected push signup.json --force         # overwrite changes made since the pull
```

`pull` records the form id and version in `.bettercollected.json` next to
the file (no secrets). `push` replaces the form only while it is still that
version, and refuses otherwise; `--force` fetches the current version first.

## Development

From `sdk/python` in the repository:

```bash
uv sync
uv run pytest
uv run python scripts/generate.py   # after docs/spec or docs/api changed
uv build                            # dist/
```

Lock with `uvx uv@0.12.23 lock`. Releases are published from CI; see
"SDK releases" in
[RELEASING.md](https://github.com/bettercollected/bettercollected/blob/develop/RELEASING.md).

## Licence

Apache-2.0. See
[LICENSE](https://github.com/bettercollected/bettercollected/blob/develop/sdk/python/LICENSE).
