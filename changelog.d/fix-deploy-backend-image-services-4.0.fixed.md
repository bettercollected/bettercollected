- Deploys through `.github/workflows/deploy.yml` now also update the `admin`, `document-sandbox`,
  `jobs-worker` and `task-runner` services. They run the backend image under their own stack service
  names and were left on their old image tag, to be updated on the stack by hand.
