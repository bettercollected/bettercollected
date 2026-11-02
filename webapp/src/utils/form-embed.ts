// Pure helpers of the embedding screens (docs/embed.md).
import { CURRENT_EMBED_SCRIPT } from '@app/lib/embed/embed-script';

/** `value` as the text of a double-quoted HTML attribute. */
export function escapeAttribute(value: string): string {
    return value.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

/** The form's name for the frame: tidied, capped, "Form" when it has none. */
function frameName(title?: string): string {
    return (title || '').replace(/\s+/g, ' ').trim().slice(0, 120) || 'Form';
}

/**
 * The code a creator pastes into their page: a placeholder carrying the form's address and the frame's
 * accessible name, and the script served by the same host as the form. The script is a versioned file that
 * never changes (lib/embed/embed-script.ts), so the tag pins it with `integrity` and `crossorigin`.
 */
export function embedSnippet(formUrl: string, title?: string): string {
    let origin = '';
    try {
        origin = new URL(formUrl).origin;
    } catch {
        origin = '';
    }
    const script = `${origin}${CURRENT_EMBED_SCRIPT.path}`;
    return `<div data-bc-form="${escapeAttribute(formUrl)}" data-bc-title="${escapeAttribute(frameName(title))}"></div>\n<script async src="${escapeAttribute(script)}" integrity="${CURRENT_EMBED_SCRIPT.integrity}" crossorigin="anonymous"></script>`;
}

/**
 * The same form without any script of ours on the page: a plain frame at a fixed height. It does not resize
 * itself and tells the page nothing; sign-in and other links still open in a new tab (`embed=1`).
 */
export function iframeSnippet(formUrl: string, title?: string, height = 640): string {
    let address = formUrl;
    try {
        const url = new URL(formUrl);
        url.searchParams.set('embed', '1');
        address = url.href;
    } catch {
        address = formUrl;
    }
    return `<iframe src="${escapeAttribute(address)}" title="${escapeAttribute(frameName(title))}" width="100%" height="${height}" style="border:0" loading="lazy" referrerpolicy="origin" allow=""></iframe>`;
}

export const EMBED_ERROR_CODES = ['invalid_origin', 'origin_scheme', 'origin_path', 'origin_wildcard', 'origin_host', 'origin_port', 'too_many_origins', 'forbidden'] as const;

/** The translation key (under common.json `STAFF.EMBED.ERROR`) of what the server answered to a save. */
export function embedErrorKey(error: unknown): string {
    const status = (error as { status?: number })?.status;
    const code = (error as { data?: { code?: string } })?.data?.code;
    if (code && (EMBED_ERROR_CODES as readonly string[]).includes(code)) return `STAFF.EMBED.ERROR.${code}`;
    if (status === 403) return 'STAFF.EMBED.ERROR.forbidden';
    return 'STAFF.EMBED.ERROR.generic';
}
