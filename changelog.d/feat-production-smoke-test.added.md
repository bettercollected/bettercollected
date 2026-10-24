- A production smoke test (`scripts/smoke/`, `docs/smoke-test.md`): a browser and the public API check
  sign-in by emailed code, creating, publishing, answering and reading back a form, the standing
  responses still decrypting, a declined deletion request as the respondent sees it, a form on a
  custom domain, the Google Forms import mode and the public endpoints, against one dedicated test
  workspace. It runs by hand in GitHub Actions (`Production smoke test`) with secrets from the
  protected `production-smoke` environment, and reports pass/fail, timings and test-workspace ids
  only.
