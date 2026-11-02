/**
 * Who may show a page of the webapp in a frame. Every page sends
 * `Content-Security-Policy: frame-ancestors 'self' <dashboard origin>`: this site, and the dashboard (its
 * form preview frames the form on the client domain, which is a different host). A published form's page
 * is the one exception and sends no framing header (it can be shown in other sites; embedding settings
 * will decide who). The header is set by the proxy (src/proxy.ts), at request time, from the running
 * server's DASHBOARD_DOMAIN and HTTP_SCHEME.
 */

// A published form's page: /<workspace>/forms/<form> (client domain; its /preview, which the builder
// frames, too) and /forms/<form> on a custom domain.
const FORM_PAGE_PATHS = [/^\/[^/]+\/forms\/[^/]+(?:\/preview)?\/?$/, /^\/forms\/[^/]+\/?$/];

/** Whether `pathname` (without the deploy base path) is a published form's page. */
export function isPublishedFormPath(pathname: string): boolean {
    return FORM_PAGE_PATHS.some((pattern) => pattern.test(pathname));
}

// scheme://host[:port] and nothing that could add a source or a directive
const ORIGIN = /^https?:\/\/[A-Za-z0-9]([A-Za-z0-9.-]*[A-Za-z0-9])?(:[0-9]{1,5})?$/;

/**
 * The `frame-ancestors` header value of a page, or null for a published form's page (no header).
 * `dashboardOrigin` is `<scheme>://<DASHBOARD_DOMAIN>`; if it is not a plain origin it is left out,
 * which only narrows the policy.
 */
export function frameAncestorsFor(pathname: string, dashboardOrigin: string): string | null {
    if (isPublishedFormPath(pathname)) return null;
    return ORIGIN.test(dashboardOrigin) ? `frame-ancestors 'self' ${dashboardOrigin}` : "frame-ancestors 'self'";
}
