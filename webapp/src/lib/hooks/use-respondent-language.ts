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

const isRespondentLanguage = (value: string | null | undefined): value is RespondentLanguage => value === 'en' || value === 'nl';

/**
 * The respondent's language: an explicit `?lang=nl|en` on the share link wins,
 * then the browser's preferred languages (the first English or Dutch one),
 * else English.
 */
export function pickRespondentLanguage(search: string, preferred: ReadonlyArray<string>): RespondentLanguage {
    const fromLink = new URLSearchParams(search).get('lang')?.toLowerCase();
    if (isRespondentLanguage(fromLink)) return fromLink;
    for (const tag of preferred) {
        const base = tag?.toLowerCase().split('-')[0];
        if (isRespondentLanguage(base)) return base;
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
