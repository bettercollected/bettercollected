- The admin portal can now trust its reverse proxy by host name: `ADMIN_TRUSTED_PROXIES`
  accepts host names next to addresses and CIDRs. The names are resolved at start and
  again every minute (`ADMIN_TRUSTED_PROXY_REFRESH_SECONDS`), so the portal keeps
  trusting a proxy whose address changed when it was recreated, instead of refusing every
  request. A name that cannot be resolved trusts nobody, and answers outside private
  networks are ignored.
