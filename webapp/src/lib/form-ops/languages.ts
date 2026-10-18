/**
 * The languages a form can declare as the language its own text is written
 * in (`settings.language`): short BCP 47 tags, each with its own name.
 * The backend keeps the same list (common/models/standard_form.py
 * FORM_LANGUAGES); the ops corpus checks that both engines take every one.
 */
import { OpError } from './model';

export const FORM_LANGUAGES = [
    { code: 'nl', name: 'Nederlands' },
    { code: 'en', name: 'English' },
    { code: 'de', name: 'Deutsch' },
    { code: 'fr', name: 'Français' },
    { code: 'es', name: 'Español' },
    { code: 'it', name: 'Italiano' },
    { code: 'pt', name: 'Português' },
    { code: 'pl', name: 'Polski' },
    { code: 'da', name: 'Dansk' },
    { code: 'sv', name: 'Svenska' },
    { code: 'nb', name: 'Norsk bokmål' },
    { code: 'fi', name: 'Suomi' }
] as const;

export type FormLanguage = (typeof FORM_LANGUAGES)[number]['code'];

const NAMES: Record<string, string> = Object.fromEntries(FORM_LANGUAGES.map(({ code, name }) => [code, name]));

/** The language's own name ("Nederlands"), or undefined when it is not one of FORM_LANGUAGES. */
export function formLanguageName(code: string | null | undefined): string | undefined {
    return code ? NAMES[code] : undefined;
}

/**
 * `value` as a form language: one of FORM_LANGUAGES (trimmed, lower case),
 * or null for null or a blank value (no language). Throws OpError for
 * anything else (backend `checked_form_language`).
 */
export function checkedFormLanguage(value: string | null | undefined): FormLanguage | null {
    if (value == null || !value.trim()) return null;
    const tag = value.trim().toLowerCase();
    if (!(tag in NAMES)) {
        throw new OpError(`'${value.trim()}' is not a language a form can be set to. Use one of: ${FORM_LANGUAGES.map((l) => l.code).join(', ')} (or null to clear it).`);
    }
    return tag as FormLanguage;
}
