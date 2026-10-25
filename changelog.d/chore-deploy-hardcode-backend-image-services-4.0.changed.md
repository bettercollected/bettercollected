- Deploys through `.github/workflows/deploy.yml` update the services that run the backend image under
  their own stack service name (`admin`, `document-sandbox`, `jobs-worker`, `task-runner`) every time;
  the `DEVELOP_`/`STAGING_`/`PROD_BACKEND_IMAGE_SERVICES` repository variables are gone. Every stack the
  workflow deploys must run these four services. Operators: delete those repository variables after
  upgrading; they are no longer read.
