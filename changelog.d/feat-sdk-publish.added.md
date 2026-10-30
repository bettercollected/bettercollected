- **The SDKs can be published to package registries**: the Python SDK and CLI as
  `bettercollected` on PyPI and the TypeScript SDK as `@bettercollected/sdk` on npm, both
  Apache-2.0, each with its own version (starting at 0.1.0) and working with
  bettercollected 4.1 or later. A tag `sdk-py-vX.Y.Z` or `sdk-ts-vX.Y.Z` starts the new
  Publish SDK workflow, which tests and builds the package, waits for an environment
  reviewer and uploads it with trusted publishing (PyPI attestations, npm provenance). The
  tags do not start the app's Build and Deploy. Steps in RELEASING.md, "SDK releases".
