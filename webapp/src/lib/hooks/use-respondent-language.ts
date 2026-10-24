'use client';

import { useEffect, useState } from 'react';

import { atom, useAtom } from 'jotai';
import { useTranslation } from 'react-i18next';

/** Languages respondent-facing text is written in. */
export type RespondentLanguage = 'en' | 'nl';

export const RESPONDENT_LANGUAGES: ReadonlyArray<{ code: RespondentLanguage; label: string }> = [
    { code: 'en', label: 'English' },
    { code: 'nl', label: 'Nederlands' }
];

/**
 * The language a value names, as one of the constants; null for anything
 * else. Returning the constant (not the value) keeps text from the URL out of
 * every attribute and link the language is used in.
 */
const asRespondentLanguage = (value: string | null | undefined): RespondentLanguage | null => (value === 'nl' ? 'nl' : value === 'en' ? 'en' : null);

/**
 * The respondent's language: an explicit `?lang=nl|en` on the share link wins,
 * then the browser's preferred languages (the first English or Dutch one),
 * else English.
 */
export function pickRespondentLanguage(search: string, preferred: ReadonlyArray<string>): RespondentLanguage {
    const fromLink = asRespondentLanguage(new URLSearchParams(search).get('lang')?.toLowerCase());
    if (fromLink) return fromLink;
    for (const tag of preferred) {
        const base = asRespondentLanguage(tag?.toLowerCase().split('-')[0]);
        if (base) return base;
    }
    return 'en';
}

// The respondent's own choice (the panel's language switch), for this visit.
const chosenLanguageAtom = atom<RespondentLanguage | null>(null);

/**
 * Language and translator for respondent-facing text (`respondent` namespace).
 * Only this text follows the respondent's language; the rest of the app is
 * unaffected. Renders English on the server and the first client pass, then
 * the detected language, so hydration always matches.
 */
export default function useRespondentLanguage() {
    const [chosen, setChosen] = useAtom(chosenLanguageAtom);
    const [detected, setDetected] = useState<RespondentLanguage>('en');

    useEffect(() => {
        const preferred = navigator.languages?.length ? navigator.languages : [navigator.language];
        setDetected(pickRespondentLanguage(window.location.search, preferred));
    }, []);

    const language = chosen ?? detected;
    const { t } = useTranslation('respondent', { lng: language });
    return { language, setLanguage: setChosen, t };
}

/** Who a shared portal view is shown to: respondents on the portal, or the team previewing it on their dashboard. */
export type PortalAudience = 'respondent' | 'team';

/**
 * Respondent-namespace text for a view shared by the portal and the team's
 * dashboard: in the respondent's language on the portal, in the app's
 * language on the dashboard.
 */
export function usePortalText(audience: PortalAudience = 'respondent') {
    const respondent = useRespondentLanguage();
    const team = useTranslation('respondent');
    if (audience === 'team') return { t: team.t, language: team.i18n.language };
    return { t: respondent.t, language: respondent.language as string };
}
