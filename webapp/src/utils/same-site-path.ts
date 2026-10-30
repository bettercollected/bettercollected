/**
 * Whether `navigateTo` is a path of this site: a relative path, no "//" or
 * "\" (browsers read "/\evil.example" as another host), no control
 * characters (URL parsers drop tabs and newlines, so "/\t/evil.example"
 * would become "//evil.example"), and resolving to this origin. Anything
 * else is never followed.
 *
 * `origin`: the origin to resolve against; the page's own in a browser. On
 * the server any fixed origin works, since only whether the path leaves it
 * matters.
 */
export function isSameSitePath(navigateTo: unknown, origin?: string): navigateTo is string {
    if (typeof navigateTo !== 'string' || !navigateTo.startsWith('/') || navigateTo.startsWith('//') || navigateTo.includes('\\')) return false;
    if (/[\u0000-\u001F\u007F]/.test(navigateTo)) return false;
    try {
        const base = origin ?? window.location.origin;
        return new URL(navigateTo, base).origin === new URL(base).origin;
    } catch {
        return false;
    }
}

/** The origin server code resolves sign-in targets against (see `isSameSitePath`). */
export const SERVER_PATH_ORIGIN = 'http://app.invalid';
