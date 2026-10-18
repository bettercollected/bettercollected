'use client';

import { useEffect } from 'react';

import useRespondentLanguage from '@app/lib/hooks/use-respondent-language';

/**
 * Sets `<html lang>` to the respondent's interface language (`?lang=`, the
 * language switch, else the browser's), so screen readers read a Dutch page
 * with Dutch pronunciation. The root layout renders `lang="en"`; leaving the
 * respondent routes puts back what was there.
 */
export default function RespondentDocumentLanguage() {
    const { language } = useRespondentLanguage();

    useEffect(() => {
        const root = document.documentElement;
        const previous = root.getAttribute('lang');
        root.setAttribute('lang', language);
        return () => {
            if (previous === null) root.removeAttribute('lang');
            else root.setAttribute('lang', previous);
        };
    }, [language]);

    return null;
}
