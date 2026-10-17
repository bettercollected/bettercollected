/**
 * Image addresses in our own storage, as far as this browser session has
 * seen them: the webapp is not told the storage host (the backend decides,
 * see backend/app/services/image_urls.py), so the builder learns its
 * addresses from what the server hands out — images on a loaded form, the
 * media library, uploads and imports. The ops engine accepts these as
 * first-party (`ApplyOptions.isStorageImageUrl`); the server checks every
 * address again when the form is saved.
 */

const MAX_REMEMBERED = 5000;
const known = new Set<string>();

/** Remember addresses the server handed out as ours. */
export function rememberStorageImageUrls(urls: Iterable<string | null | undefined>) {
    for (const url of urls) {
        if (typeof url !== 'string') continue;
        const trimmed = url.trim();
        if (!/^https?:\/\//i.test(trimmed)) continue;
        if (known.size >= MAX_REMEMBERED && !known.has(trimmed)) known.delete(known.values().next().value as string);
        known.add(trimmed);
    }
}

/** Has the server handed out this address as one of our images? */
export function isStorageImageUrl(url: string): boolean {
    return known.has(url.trim());
}
