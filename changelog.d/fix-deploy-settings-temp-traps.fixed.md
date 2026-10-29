- `deploy.sh` no longer leaves a copy of your secrets in the system temporary directory when it is
  interrupted (Ctrl-C, `kill`, a closed terminal). `settings-prune` copies `.env` and `.env.deployment` there
  for its container, and `settings-env-export` writes the exported values there. Both, and the other steps
  that edit a copy of `.env` or `.env.deployment`, now remove their scratch files on every way out, and
  stop their container first. A `kill` sent to the script alone now ends it at once instead of after the
  container.
