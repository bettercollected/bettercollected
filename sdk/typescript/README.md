# BetterCollected TypeScript SDK

A small typed client for the
[BetterCollected public API](https://github.com/bettercollected/bettercollected/blob/develop/docs/api/README.md).
It uses `fetch` and nothing else at runtime; the types are generated from the
form spec JSON Schema and the API's OpenAPI document.

Works with bettercollected 4.1 or later, on bettercollected.com or on your
own instance. Node.js 22 or later; the package is ES modules only.

- Documentation: https://bettercollected.com/developers/
- Source: https://github.com/bettercollected/bettercollected/tree/develop/sdk/typescript
- Issues: https://github.com/bettercollected/bettercollected/issues

## Install

```bash
npm install @bettercollected/sdk
```

## API key

A workspace admin creates an API key on the dashboard's **AI → MCP** tab
(`/<workspace>/dashboard/ai/mcp`). A key works in its own workspace only and
never does more than the person who created it may do. Keep it on the server:
never ship it to a browser.

## Quick start

```ts
import { BetterCollected, BetterCollectedError } from "@bettercollected/sdk";

const bc = new BetterCollected({ apiKey: process.env.BETTERCOLLECTED_API_KEY!, baseUrl: "https://forms.example.org" });
const { formId, etag } = await bc.createForm({ specVersion: "1", title: "Sign-up", pages: [{ id: "p1", fields: [] }] }, { idempotencyKey: "signup-v1" });
await bc.applyOps(formId, [{ op: "add_field", pageId: "p1", field: { title: "Your email", type: "email", required: true } }], { ifMatch: etag });
try {
  await bc.publishForm(formId);
} catch (error) {
  if (error instanceof BetterCollectedError) console.error(error.code, error.errors);
}
```

`baseUrl` is the address of your instance.

Methods: `listForms`, `createForm`, `validateForm`, `getForm`,
`replaceForm`, `previewReplace`, `applyOps`, `dryRunOps`, `publishForm`,
`listResponses`, `getResponse`. Reads that return a version give
`{ value, etag }`; pass the `etag` as `ifMatch` to change exactly that
version. Errors are `BetterCollectedError` with `status`, `code`, `errors`
and, on 429, `retryAfter`.

For forms as code from the command line, use the `bettercollected` command
from the Python package (`pip install bettercollected`).

## Development

From `sdk/typescript` in the repository, with Node 22.18 or later (the tests
run TypeScript directly):

```bash
npm ci --ignore-scripts
npm run generate   # after docs/api or docs/spec changed
npm run typecheck && npm test
npm run build      # dist/
npm pack --dry-run # what a release ships
```

Releases are published from CI; see "SDK releases" in
[RELEASING.md](https://github.com/bettercollected/bettercollected/blob/develop/RELEASING.md).

## Licence

Apache-2.0. See
[LICENSE](https://github.com/bettercollected/bettercollected/blob/develop/sdk/typescript/LICENSE).
