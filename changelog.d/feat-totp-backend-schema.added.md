- Groundwork for an authenticator app (TOTP) as a second factor for staff: two new tables for the
  factor and its recovery codes, `/auth/mfa/*` routes to set one up, check a code, make new
  recovery codes and turn it off, and the sealed secret. It is behind `TOTP_ENABLED`, which is
  off by default: while it is off the routes answer 422, nobody is asked for a second factor and
  nothing else changes.
