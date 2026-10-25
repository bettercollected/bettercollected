- Deploys through `.github/workflows/deploy.yml` can now also update the stack services that run the
  backend image under their own name (`admin`, `document-sandbox`, `jobs-worker`, `task-runner`). They were
  always left on their old image tag. Each environment lists the ones its stack runs in a new repository
  variable (`DEVELOP_BACKEND_IMAGE_SERVICES`, `STAGING_BACKEND_IMAGE_SERVICES`, `PROD_BACKEND_IMAGE_SERVICES`;
  empty by default, so nothing changes until it is set). See "CI deployments" in the README.
