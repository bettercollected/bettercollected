/**
 * Image addresses a form may hold (backend services/image_urls.py and
 * services/form_images.py): our own storage, Unsplash photos by their
 * canonical address, the builder's built-in placeholders — or an address the
 * form already holds.
 *
 * Our storage's address depends on the server's configuration, so it is
 * recognised only through `ApplyOptions.isStorageImageUrl`. An Unsplash
 * address is kept as given; the server stores it with its sizing parameters
 * cleaned up, and an address of our own Unsplash route is refused here but
 * turned into the canonical one by the server.
 */
import type { ApplyOptions, FormDoc, FormField } from './types';

export const IMAGE_URL_ERROR = "Images must come from this form's own storage or from Unsplash (https://images.unsplash.com); other image addresses are refused. Upload the image, or copy it in from its address first.";

export const BUILTIN_IMAGE_URLS = new Set(['https://s3.eu-central-1.wasabisys.com/bettercollected/images/v2_layout_image.webp', 'https://s3.eu-central-1.wasabisys.com/bettercollected/images/Default_field_image.png']);

const MAX_IMAGE_URL_LENGTH = 2048;
const UNSAFE = /[\s\x00-\x1f\x7f"'<>\\`()]/;
const PHOTO_PATH = /^(?:[A-Za-z0-9][A-Za-z0-9_-]{0,199}\/)?[A-Za-z0-9][A-Za-z0-9_.-]{0,199}$/;

function isUnsplashPhoto(url: string): boolean {
    let parsed: URL;
    try {
        parsed = new URL(url);
    } catch {
        return false;
    }
    if (parsed.protocol !== 'https:' || parsed.host.toLowerCase() !== 'images.unsplash.com' || parsed.username || parsed.password || parsed.hash) return false;
    const path = parsed.pathname.slice(1);
    return PHOTO_PATH.test(path) && !path.includes('..') && path.length <= 300;
}

/** The address to store for `url` when it is first-party, else null (backend `first_party_image_url`). */
export function firstPartyImageUrl(url: unknown, options: ApplyOptions = {}): string | null {
    if (typeof url !== 'string') return null;
    const trimmed = url.trim();
    if (!trimmed || trimmed.length > MAX_IMAGE_URL_LENGTH || UNSAFE.test(trimmed)) return null;
    if (BUILTIN_IMAGE_URLS.has(trimmed) || isUnsplashPhoto(trimmed)) return trimmed;
    if (options.isStorageImageUrl?.(trimmed)) return trimmed;
    return null;
}

/** Every non-blank image address on a form (backend `form_image_urls`). */
export function formImageUrls(doc: FormDoc): Set<string> {
    const found = new Set<string>();
    const add = (url: unknown) => {
        if (typeof url === 'string' && url.trim()) found.add(url.trim());
    };
    const theme = (t: any) => add(t?.background?.imageUrl);
    const fields = (list: FormField[] | undefined) => {
        for (const field of list ?? []) {
            if (!field) continue;
            add((field as any).imageUrl);
            theme(field.properties?.theme);
            fields(field.properties?.fields as FormField[] | undefined);
        }
    };
    theme(doc.theme);
    add(doc.welcomePage?.imageUrl);
    for (const ending of doc.thankyouPage ?? []) add(ending?.imageUrl);
    add(doc.coverImage);
    fields(doc.fields);
    return found;
}
