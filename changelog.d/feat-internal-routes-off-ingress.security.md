- The API's key-only internal routes (the data task runner's admin-task routes and the Temporal
  worker's and actions executor's job routes) are no longer reachable through the public
  ingress. The backend serves them on a second, never-published listener (`API_INTERNAL_PORT`,
  8001) and answers 404, before any key is checked, to a request that carries proxy headers. The
  admin-task routes answer on the internal listener only; the worker routes still accept direct
  requests from private addresses on port 8000 until `API_INTERNAL_ROUTES=internal_port` is set.
  Operators: point the worker's `SERVER_URL` (and, outside `deploy.sh`, the task runner's
  `ADMIN_TASKS_BACKEND_URL`) at `http://backend:8001/api/v1`, never publish port 8001, and make
  your proxy add `X-Forwarded-For`. Then set `API_INTERNAL_ROUTES=internal_port`: a Swarm or
  ingress-mesh stack, and any stack whose port 8000 is reachable from outside, must, because
  `direct` lets through outside callers whose address a proxy, Docker's userland-proxy or the
  ingress mesh rewrites to a private one (the backend warns at startup while it is `direct`).
  TODO for 4.1: make `internal_port` the default (docs/admin-service.md, "Internal routes").
