- The admin portal can take the client address from Cloudflare's
  `CF-Connecting-IP` header, so its address allow-list can name the operators'
  own addresses behind Cloudflare. It is off unless `ADMIN_TRUST_CLOUDFLARE` is
  set, and then the header is believed only for a request that came through a
  proxy in `ADMIN_TRUSTED_PROXIES` from a Cloudflare address
  (`ADMIN_CLOUDFLARE_IPS` replaces the built-in ranges). From any other source,
  sent twice or malformed, it is ignored.
