import { pickMailLocale } from '@app/utils/mail-locale';

/**
 * The language of the staff dashboard (what the account menu's switch offers).
 * The dashboard's own text exists in English and Dutch; respondent-facing text
 * follows the respondent's language (use-respondent-language.ts), never this.
 */
export type StaffLanguage = 'en' | 'nl';

export const STAFF_LANGUAGES: ReadonlyArray<{ code: StaffLanguage; label: string }> = [
    { code: 'en', label: 'English' },
    { code: 'nl', label: 'Nederlands' }
];

/** Where the person's own choice is kept: this browser only. */
export const STAFF_LANGUAGE_STORAGE_KEY = 'bettercollected.staff-language';

/** `value` as one of the constants, or null for anything else (so nothing stored or typed is ever used as it is). */
export function asStaffLanguage(value: unknown): StaffLanguage | null {
    return value === 'nl' ? 'nl' : value === 'en' ? 'en' : null;
}

/**
 * The staff language: the person's own choice when there is one, else the first
 * English or Dutch language the browser prefers (Dutch for nl, nl-NL, nl-BE, …),
 * else English.
 */
export function pickStaffLanguage(chosen: unknown, preferred: ReadonlyArray<string | undefined | null>): StaffLanguage {
    return asStaffLanguage(chosen) ?? pickMailLocale(preferred);
}

/** The browser's preferred languages (none on the server). */
export function browserLanguages(): string[] {
    if (typeof navigator === 'undefined') return [];
    return navigator.languages?.length ? [...navigator.languages] : navigator.language ? [navigator.language] : [];
}

/** The language this browser's person chose, or null (nothing chosen, or storage blocked). */
export function readChosenStaffLanguage(): StaffLanguage | null {
    try {
        return asStaffLanguage(window.localStorage.getItem(STAFF_LANGUAGE_STORAGE_KEY));
    } catch {
        return null;
    }
}

/** Remember the choice in this browser; a blocked or full storage only means it is not remembered. */
export function storeChosenStaffLanguage(language: StaffLanguage): void {
    try {
        window.localStorage.setItem(STAFF_LANGUAGE_STORAGE_KEY, language);
    } catch {
        // private window, blocked site data: the choice holds for this visit only
    }
}
