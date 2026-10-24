/**
 * `?lang=en|nl` to carry a respondent's chosen language from one portal URL to
 * the next (the root redirect, the tab links), or '' for anything else. Only
 * this one parameter is kept, and only a language the portal speaks.
 */
export function respondentLangQuery(value: string | string[] | null | undefined): string {
    const lang = (Array.isArray(value) ? value[0] : value)?.toLowerCase();
    // Constant results: nothing from the URL is copied into the next link.
    if (lang === 'nl') return '?lang=nl';
    if (lang === 'en') return '?lang=en';
    return '';
}

/**
 * The sign-in page for a respondent of a workspace. It carries the
 * respondent's language, so the sign-in page asks for the code mail in it.
 */
export function respondentSignInUrl(workspaceId: string | undefined, redirectTo: string | null | undefined, language: string): string {
    const params = new URLSearchParams({ type: 'responder', workspace_id: workspaceId ?? '', redirect_to: redirectTo ?? '' });
    if (language === 'en' || language === 'nl') params.set('lang', language);
    return `/login?${params.toString()}`;
}
