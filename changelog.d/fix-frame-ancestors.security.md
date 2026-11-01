- Every page of the webapp except a published form's page now sends
  `Content-Security-Policy: frame-ancestors 'self'` plus the dashboard's own origin, so no
  other site can show the staff dashboard, the sign-in page or a respondent's submissions
  in a frame. They carried `X-Frame-Options: ALLOW-FROM https://undefined` instead, a value
  no browser honours, so any site could frame them. The header is now set per request from
  the running server's `DASHBOARD_DOMAIN` and `HTTP_SCHEME`, on the dashboard, client and
  custom domains and on a single-domain setup alike. Published form pages are unchanged.
