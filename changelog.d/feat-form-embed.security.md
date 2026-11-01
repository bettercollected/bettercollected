- The dashboard pages now carry `frame-ancestors 'self'`, so no other site can show them in a
  frame. The `X-Frame-Options: ALLOW-FROM` header they carried is ignored by every current
  browser.
