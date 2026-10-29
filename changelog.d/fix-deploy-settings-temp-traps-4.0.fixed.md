- `deploy.sh` removes every scratch file or directory that holds a secret (the copies of `.env` and
  `.env.deployment` used by the settings prune and the Umami blanking, the settings export, the
  worker keys, the replacement of `.env`) when it is stopped by Ctrl-C, `kill` or a closed terminal,
  and stops the one-off container first. A failed write while blanking `UMAMI_PASSWORD` in
  `.env.deployment` or creating a service's env file is now reported instead of being passed over.
