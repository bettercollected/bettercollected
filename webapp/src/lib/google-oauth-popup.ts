/**
 * The Google Sheets connection runs in a popup: Google sends the browser back
 * to the callback page (integrations/google/callback), which hands the
 * result to the dashboard window that opened it and closes.
 *
 * - The callback posts only to the dashboard origin (never `'*'`), and only
 *   the parameters the dashboard needs.
 * - The dashboard accepts a message only from the dashboard origin and only
 *   from the popup it opened.
 */

export interface OauthCallbackResult {
    code?: string;
    state?: string;
    error?: string;
}

const KEYS: Array<keyof OauthCallbackResult> = ['code', 'state', 'error'];

/** The origin of `${scheme}${domain}` (e.g. "https://" + "admin.example.com"), or null. */
export function dashboardOrigin(scheme?: string | null, domain?: string | null): string | null {
    if (!scheme || !domain) return null;
    try {
        const url = new URL(`${scheme}${domain}`);
        if (url.protocol !== 'http:' && url.protocol !== 'https:') return null;
        return url.origin;
    } catch {
        return null;
    }
}

/** The dashboard origin of the running app's public config, or null. */
export function configuredDashboardOrigin(): string | null {
    if (typeof window === 'undefined') return null;
    return dashboardOrigin(window.PUBLIC_CONFIG?.HTTP_SCHEME, window.PUBLIC_CONFIG?.DASHBOARD_DOMAIN);
}

/** What the callback page passes on: the code, the state, or Google's error. */
export function oauthCallbackResult(params: { get(name: string): string | null } | null | undefined): OauthCallbackResult {
    const result: OauthCallbackResult = {};
    for (const key of KEYS) {
        const value = params?.get(key);
        if (value) result[key] = value;
    }
    return result;
}

/**
 * The callback's result when `event` comes from `popup` on the dashboard
 * origin; null for any other message.
 */
export function oauthMessage(event: MessageEvent, expectedOrigin: string | null, popup: Window | null): OauthCallbackResult | null {
    if (!expectedOrigin || event.origin !== expectedOrigin) return null;
    if (!popup || event.source !== popup) return null;
    const data = event.data;
    if (!data || typeof data !== 'object') return null;
    const result: OauthCallbackResult = {};
    for (const key of KEYS) {
        if (typeof data[key] === 'string' && data[key]) result[key] = data[key];
    }
    return result;
}
