/**
 * `?lang=en|nl` to carry a respondent's chosen language from one portal URL to
 * the next (the root redirect, the tab links), or '' for anything else. Only
 * this one parameter is kept, and only a language the portal speaks.
 */
export function respondentLangQuery(value: string | string[] | null | undefined): string {
    const lang = (Array.isArray(value) ? value[0] : value)?.toLowerCase();
    return lang === 'en' || lang === 'nl' ? `?lang=${lang}` : '';
}
