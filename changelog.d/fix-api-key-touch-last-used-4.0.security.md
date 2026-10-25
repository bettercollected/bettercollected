- A workspace API key revoked while a request using it was in flight stays revoked: recording the
  key's last use now changes only that field, and only while the key is not revoked (a conditional
  update in MongoDB and Postgres), instead of saving the request's copy of the whole key, which
  could set it back to not revoked. Such a request is refused.
