// Pure helpers of the webhooks screens (docs/webhooks.md): the same address
// rules the server applies (the server decides; this only tells people early),
// and the translation keys of what it answers.

export const URL_MAX = 2048;
export const MAX_FIELDS = 100;
export const KEY_PATTERN = /^[A-Za-z_][A-Za-z0-9_]{0,63}$/;

export const ERROR_CODES = [
    'webhooks_off',
    'invalid_url',
    'not_https',
    'not_allowed',
    'unreachable',
    'invalid_key',
    'unknown_variable',
    'variable_not_supported',
    'file_not_sent',
    'too_many_fields',
    'too_many_webhooks',
    'rate_limited',
    'forbidden',
    'not_found'
] as const;

export const DELIVERY_ERROR_CODES = [
    'http_4xx',
    'http_5xx',
    'timeout',
    'unreachable',
    'tls_error',
    'redirect_refused',
    'not_allowed',
    'invalid_url',
    'too_large',
    'secret_unreadable',
    'answers_unreadable',
    'disabled',
    'internal_error'
] as const;

const isKnown = (list: readonly string[], code: unknown): code is string => typeof code === 'string' && list.includes(code);

/** The code of a failed call: the API's `code`, else one from the HTTP status. */
export function errorCodeOf(error: any): string {
    const code = error?.data?.code;
    if (typeof code === 'string') return code;
    switch (error?.status) {
        case 403:
            return 'forbidden';
        case 404:
            return 'not_found';
        case 429:
            return 'rate_limited';
        default:
            return 'unknown';
    }
}

export const errorKey = (code: unknown) => `WEBHOOKS.ERROR.${isKnown(ERROR_CODES, code) ? code : 'unknown'}`;

export const deliveryErrorKey = (code?: string | null) => `WEBHOOKS.DELIVERIES.ERROR.${isKnown(DELIVERY_ERROR_CODES, code) ? code : 'unknown'}`;

/** Which field of the form a refusal belongs to (so it sits next to it), or null for the form as a whole. */
export function errorField(code: string): 'url' | 'fields' | null {
    switch (code) {
        case 'invalid_url':
        case 'not_https':
        case 'not_allowed':
        case 'unreachable':
            return 'url';
        case 'invalid_key':
        case 'unknown_variable':
        case 'variable_not_supported':
        case 'file_not_sent':
        case 'too_many_fields':
            return 'fields';
        default:
            return null;
    }
}

/**
 * What is wrong with an address before it is sent, or null. Mirrors the
 * server's syntax rules (https, no credentials, default port, no fragment);
 * the server still checks what the name resolves to.
 */
export function urlProblem(value: string): 'empty' | 'not_https' | 'invalid_url' | null {
    const text = value.trim();
    if (!text) return 'empty';
    if (text.length > URL_MAX || /[\s\\]/.test(text)) return 'invalid_url';
    let parsed: URL;
    try {
        parsed = new URL(text);
    } catch {
        return /^[a-z][a-z0-9+.-]*:/i.test(text) ? 'invalid_url' : 'not_https';
    }
    if (parsed.protocol !== 'https:') return 'not_https';
    if (parsed.username || parsed.password || text.includes('@')) return 'invalid_url';
    if (parsed.port && parsed.port !== '443') return 'invalid_url';
    if (!parsed.hostname || !parsed.hostname.includes('.') || /^[\d.]+$/.test(parsed.hostname) || parsed.hostname.startsWith('[')) return 'invalid_url';
    return null;
}

export const defaultKeyOf = (source: string) => source.replace(/[^A-Za-z0-9_]/g, '_');
export const isValidKey = (key: string) => KEY_PATTERN.test(key);

export const WAITING_STATUSES = ['pending', 'in_progress', 'retrying'] as const;

/** A time in the reader's language, or an empty string when there is none. */
export function formatDateTime(value: string | null | undefined, language: string): string {
    if (!value) return '';
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? '' : date.toLocaleString(language, { dateStyle: 'medium', timeStyle: 'short' });
}

/** `850 ms`, `2.4 s`; empty when unknown. */
export function formatDuration(ms: number | null | undefined): string {
    if (ms === null || ms === undefined) return '';
    return ms < 1000 ? `${ms} ms` : `${(ms / 1000).toFixed(1)} s`;
}
