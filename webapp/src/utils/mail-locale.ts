/**
 * The language of a mail the dashboard asks the backend to send: a sign-in
 * code or a workspace invitation. Mail templates exist in English and Dutch;
 * the backend sends English unless it is asked for Dutch.
 */
export type MailLocale = 'en' | 'nl';

export const MAIL_LOCALES: ReadonlyArray<{ code: MailLocale; label: string }> = [
    { code: 'en', label: 'English' },
    { code: 'nl', label: 'Nederlands' }
];

/** The first English or Dutch language among the given language tags (the browser's preferred languages), else English. */
export function pickMailLocale(preferred: ReadonlyArray<string | undefined | null>): MailLocale {
    for (const tag of preferred) {
        const base = tag?.toLowerCase().split('-')[0];
        if (base === 'en' || base === 'nl') return base;
    }
    return 'en';
}

/**
 * The browser's mail language. The dashboard itself has no language setting
 * yet, so a sign-in code follows the browser, as the respondent pages do.
 */
export function browserMailLocale(): MailLocale {
    if (typeof navigator === 'undefined') return 'en';
    return pickMailLocale(navigator.languages?.length ? navigator.languages : [navigator.language]);
}
