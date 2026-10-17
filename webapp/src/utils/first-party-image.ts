import type { ImageLoaderProps } from 'next/image';

import environments from '@app/configs/environments';

/**
 * Images on respondent pages only ever come from us. An Unsplash photo is
 * served through our API (`GET /images/unsplash/<photo>`, which fetches it
 * once and keeps a copy in our storage), so a respondent's browser never
 * contacts images.unsplash.com. Forms store the photo's canonical Unsplash
 * address (it names no host of ours), and every render path rewrites it here
 * to this webapp's own API host. The backend's allow-list is
 * backend/app/services/image_urls.py.
 */

const UNSPLASH_HOST = 'images.unsplash.com';
// the sizing options our route accepts; Unsplash's tracking ones are dropped
const ROUTE_PARAMS = ['auto', 'crop', 'fit', 'fm', 'h', 'q', 'w'] as const;
const PARAM_VALUE: Record<(typeof ROUTE_PARAMS)[number], RegExp> = {
    auto: /^[a-z,]{1,40}$/,
    crop: /^[a-z,]{1,80}$/,
    fit: /^[a-z]{1,10}$/,
    fm: /^[a-z]{1,5}$/,
    h: /^\d{1,5}$/,
    q: /^\d{1,3}$/,
    w: /^\d{1,5}$/
};
const PHOTO_PATH = /^(?:[A-Za-z0-9][A-Za-z0-9_-]{0,199}\/)?[A-Za-z0-9][A-Za-z0-9_.-]{0,199}$/;

export function unsplashRouteBase(apiHost: string = environments.API_ENDPOINT_HOST): string {
    return `${apiHost.replace(/\/+$/, '')}/images/unsplash/`;
}

/** Our address for an images.unsplash.com photo, or null for anything else. */
export function unsplashRouteUrl(url: string, apiHost?: string): string | null {
    let parsed: URL;
    try {
        parsed = new URL(url.trim());
    } catch {
        return null;
    }
    if (parsed.protocol !== 'https:' || parsed.hostname !== UNSPLASH_HOST || parsed.port || parsed.username || parsed.password) return null;
    const path = parsed.pathname.replace(/^\//, '');
    if (!PHOTO_PATH.test(path) || path.includes('..')) return null;
    const kept = new URLSearchParams();
    for (const key of ROUTE_PARAMS) {
        const values = parsed.searchParams.getAll(key);
        if (values.length === 1 && PARAM_VALUE[key].test(values[0].toLowerCase())) kept.set(key, values[0].toLowerCase());
    }
    const query = kept.toString();
    return unsplashRouteBase(apiHost) + path + (query ? `?${query}` : '');
}

/** The address to load an image from: an Unsplash photo through our route,
 * anything else as stored. */
export function firstPartyImageUrl(url?: string | null, apiHost?: string): string {
    if (!url) return '';
    return unsplashRouteUrl(url, apiHost) ?? url;
}

export function isUnsplashRouteUrl(url?: string | null, apiHost?: string): boolean {
    return !!url && url.startsWith(unsplashRouteBase(apiHost));
}

/** next/image loader for our Unsplash route: the route sizes the photo
 * itself (and rounds to a fixed set of widths), so no optimiser is involved. */
export function unsplashRouteLoader({ src, width, quality }: ImageLoaderProps): string {
    const [base, query = ''] = src.split('?');
    const params = new URLSearchParams(query);
    params.set('w', String(width));
    params.set('q', String(quality || 75));
    return `${base}?${params.toString()}`;
}

/** `src` and `loader` for a next/image of a stored image address. */
export function firstPartyImageProps(url?: string | null): { src: string; loader?: (props: ImageLoaderProps) => string } {
    const src = firstPartyImageUrl(url);
    return isUnsplashRouteUrl(src) ? { src, loader: unsplashRouteLoader } : { src };
}
