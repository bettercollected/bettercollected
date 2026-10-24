/**
 * Paths on the responder portal, built in one place.
 *
 * A workspace handle, form slug or submission id comes from a route, the API
 * or what a respondent typed. Each is percent-encoded as ONE path segment, so
 * none can add a segment, start a new host ("//evil.com" would make a
 * protocol-relative URL) or a scheme ("javascript:"): every path starts with a
 * single "/" followed by an encoded segment, and stays on this site.
 */

type Segment = string | number | null | undefined;

/**
 * One value as one path segment. A value that arrives already percent-encoded
 * (a route parameter) is decoded first, so it is encoded exactly once.
 */
export function portalSegment(value: Segment): string {
    const text = value === null || value === undefined ? '' : String(value);
    let decoded = text;
    try {
        decoded = decodeURIComponent(text);
    } catch {
        // Not valid percent-encoding: encode it as it is.
    }
    return encodeURIComponent(decoded);
}

/**
 * The portal's root: "/<workspace>" on the shared forms domain, "" on a
 * workspace's custom domain (and when there is no handle).
 */
export function portalBase(workspaceName: Segment, hasCustomDomain: boolean): string {
    if (hasCustomDomain) return '';
    const handle = portalSegment(workspaceName);
    return handle ? `/${handle}` : '';
}

/** A path under the portal's root, e.g. portalPath('acme', false, 'forms', slug) -> "/acme/forms/<slug>". */
export function portalPath(workspaceName: Segment, hasCustomDomain: boolean, ...segments: Segment[]): string {
    // Empty segments are left out: "//" must never appear.
    const rest = segments.map(portalSegment).filter(Boolean).join('/');
    return `${portalBase(workspaceName, hasCustomDomain)}/${rest}`;
}
