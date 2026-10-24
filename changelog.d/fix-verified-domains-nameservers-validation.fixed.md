- `VERIFIED_DOMAINS_NAMESERVERS` takes IP addresses only (IPv4 or IPv6, comma-separated, spaces
  around them tolerated). A host name or another separator such as `;` used to make every domain
  lookup, and so every hourly re-check, fail. Now the admin portal refuses such a value, and in a
  service's environment it stops the backend and the jobs worker at start with an error naming the
  setting. A value stored earlier that isn't a list of addresses is ignored with an error in the
  log, and the system resolver is used until it is corrected.
