import type { TFunction } from 'i18next';

import { scopeLabelKey } from './key-limits-fields';
import { KEY_ERROR_CODES, errorCode, scopeNamedBy } from './key-rules';

// The server's answer to a refused request as text: a string as it is, an object by its message
// (e.g. {code: 'submissions_api_off', message}), nothing else.
export function errorText(data: unknown): string | undefined {
    if (typeof data === 'string' && data.trim()) return data;
    const message = (data as { message?: unknown; detail?: unknown } | null | undefined)?.message ?? (data as { detail?: unknown } | null | undefined)?.detail;
    return typeof message === 'string' && message.trim() ? message : undefined;
}

/**
 * What to tell the person about a refused key request: the text of its `code` in the language of the screen (every
 * code the key routes answer with has one), else the server's own message, else `fallbackKey`. A scope the refusal
 * names is said by its label, not its machine name.
 */
export function keyErrorText(t: TFunction, error: unknown, fallbackKey: string): string {
    const data = (error as { data?: unknown } | null | undefined)?.data;
    const code = errorCode(data);
    const key = code ? KEY_ERROR_CODES[code] : undefined;
    if (key) {
        const scope = scopeNamedBy(data);
        return t(key, { scope: scope ? t(scopeLabelKey(scope)) : '' });
    }
    return errorText(data) || t(fallbackKey);
}
