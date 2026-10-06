'use client';

import React, { useMemo } from 'react';
import i18n from 'i18next';
import { initReactI18next, I18nextProvider } from 'react-i18next';
import commonEn from '../../../public/locales/en/common.json';
import builderEn from '../../../public/locales/en/builder.json';
import respondentEn from '../../../public/locales/en/respondent.json';
import respondentNl from '../../../public/locales/nl/respondent.json';

// Initialize i18next if not already initialized
if (!i18n.isInitialized) {
    i18n.use(initReactI18next).init({
        resources: {
            en: {
                common: commonEn,
                builder: builderEn,
                respondent: respondentEn
            },
            // Respondent-facing text is Dutch and English: the form's privacy
            // panel and question notes read it in the respondent's language
            // (lib/hooks/use-respondent-language.ts) without switching the
            // rest of the app.
            nl: {
                respondent: respondentNl
            }
        },
        lng: 'en',
        fallbackLng: 'en',
        ns: ['common', 'builder', 'respondent'],
        defaultNS: 'common',
        interpolation: {
            escapeValue: false
        },
        react: {
            useSuspense: false
        }
    });
}

export default function I18nProvider({ children }: { children: React.ReactNode }) {
    return <I18nextProvider i18n={i18n}>{children}</I18nextProvider>;
}
