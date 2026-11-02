// Pure helpers of the embedding screens (docs/embed.md).

/** `value` as the text of a double-quoted HTML attribute. */
export function escapeAttribute(value: string): string {
    return value.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

/**
 * The code a creator pastes into their page: a placeholder carrying the form's address and the frame's
 * accessible name, and the script served by the same host as the form.
 */
export function embedSnippet(formUrl: string, title?: string): string {
    let scriptUrl = '';
    try {
        scriptUrl = `${new URL(formUrl).origin}/embed.js`;
    } catch {
        scriptUrl = '/embed.js';
    }
    const name = (title || '').replace(/\s+/g, ' ').trim().slice(0, 120) || 'Form';
    return `<div data-bc-form="${escapeAttribute(formUrl)}" data-bc-title="${escapeAttribute(name)}"></div>\n<script async src="${escapeAttribute(scriptUrl)}"></script>`;
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
