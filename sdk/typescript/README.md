# BetterCollected TypeScript SDK

A small typed client for the [public API](../../docs/api/README.md). It uses
`fetch` and nothing else at runtime; the types are generated from the form
spec JSON Schema and the API's OpenAPI document.

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

Methods: `listForms`, `createForm`, `validateForm`, `getForm`,
`replaceForm`, `previewReplace`, `applyOps`, `dryRunOps`, `publishForm`,
`listResponses`, `getResponse`. Reads that return a version give
`{ value, etag }`; pass the `etag` as `ifMatch` to change exactly that
version. Errors are `BetterCollectedError` with `status`, `code`, `errors`
and, on 429, `retryAfter`.

## Development

Node 22.18 or later (the tests run TypeScript directly).

```bash
npm ci --ignore-scripts
npm run generate   # after docs/api or docs/spec changed
npm run typecheck && npm test
npm run build      # dist/
```

The package is not published to a registry yet.
