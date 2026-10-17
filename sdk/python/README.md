# BetterCollected Python SDK and CLI

A small typed client for the [public API](../../docs/api/README.md)
(`httpx` and Pydantic), and the `bettercollected` command line tool for
keeping forms as code. The models are generated from the form spec JSON
Schema and the API's OpenAPI document.

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

Reads that return a version give `Versioned(value, etag)`; pass the `etag`
as `if_match` to change exactly that version.

## Forms as code

JSON is the canonical format; YAML (`.yaml`, `.yml`) works too. The API key
is read from `BETTERCOLLECTED_API_KEY` only; the instance from `--url` or
`BETTERCOLLECTED_URL`.

```bash
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

```bash
uv sync
uv run pytest
uv run python scripts/generate.py   # after docs/spec or docs/api changed
```

Lock with `uvx uv@0.12.23 lock`. The package is not published to a
registry yet.
