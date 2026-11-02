/**
 * Who may show a page of the webapp in a frame. Every page sends
 * `Content-Security-Policy: frame-ancestors 'self' <dashboard origin>`: this site, and the dashboard (its
 * form preview frames the form on the client domain, which is a different host). The one exception, a
 * published form's page on the form domain or a custom domain, is decided by the proxy (src/proxy.ts,
 * lib/server/embed-policy.ts), not here: a form-shaped path on any other host (the dashboard's) is not a
 * published form's page and gets this rule. The header is set at request time from the running server's
 * DASHBOARD_DOMAIN and HTTP_SCHEME.
 */

// scheme://host[:port] and nothing that could add a source or a directive
const ORIGIN = /^https?:\/\/[A-Za-z0-9]([A-Za-z0-9.-]*[A-Za-z0-9])?(:[0-9]{1,5})?$/;

/**
 * The `frame-ancestors` header value of a page. `dashboardOrigin` is `<scheme>://<DASHBOARD_DOMAIN>`; if it
 * is not a plain origin it is left out, which only narrows the policy.
 */
export function frameAncestorsFor(dashboardOrigin: string): string {
    return ORIGIN.test(dashboardOrigin) ? `frame-ancestors 'self' ${dashboardOrigin}` : "frame-ancestors 'self'";
}
