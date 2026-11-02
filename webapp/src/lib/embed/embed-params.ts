/**
 * Embed mode of a respondent page (docs/embed.md): the page is shown in a frame on another site, which
 * is announced in the address as `?embed=1&parent=<that site's origin>` (the embed script adds both).
 * Nothing else about the address is trusted: `parent` is only ever the one origin the page posts its
 * lifecycle messages to, and only when the page really is in a frame.
 */
export interface EmbedContext {
    /** The page was asked to render for a frame (`embed=1`). */
    embedded: boolean;
    /** The only origin messages go to; null when none was given (then none are sent). */
    parentOrigin: string | null;
}

export const NOT_EMBEDDED: EmbedContext = { embedded: false, parentOrigin: null };

/** `value` as an `http(s)` origin (scheme, host, port; nothing else), or null. */
export function asOrigin(value: string | null | undefined): string | null {
    if (!value) return null;
    let url: URL;
    try {
        url = new URL(value);
    } catch {
        return null;
    }
    if (url.protocol !== 'https:' && url.protocol !== 'http:') return null;
    // only an origin as given: no path, query, fragment or credentials riding along
    if (url.origin !== value) return null;
    return url.origin;
}

export function readEmbedContext(search: string): EmbedContext {
    const params = new URLSearchParams(search);
    if (params.get('embed') !== '1') return NOT_EMBEDDED;
    return { embedded: true, parentOrigin: asOrigin(params.get('parent')) };
}
