/**
 * `value` as an absolute http(s) URL, or null. For creator-supplied links
 * rendered as an `href` (a form's privacy policy): anything else
 * (`javascript:`, `data:`, relative paths) is not rendered.
 */
export function httpUrl(value: unknown): string | null {
    const text = typeof value === 'string' ? value.trim() : '';
    if (!text) return null;
    try {
        const url = new URL(text);
        return url.protocol === 'http:' || url.protocol === 'https:' ? url.href : null;
    } catch {
        return null;
    }
}
