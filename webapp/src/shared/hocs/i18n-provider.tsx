'use client';

import React, { useMemo } from 'react';
import i18n from 'i18next';
import { initReactI18next, I18nextProvider } from 'react-i18next';
import commonEn from '../../../public/locales/en/common.json';
import builderEn from '../../../public/locales/en/builder.json';

// Initialize i18next if not already initialized
if (!i18n.isInitialized) {
    i18n.use(initReactI18next).init({
        resources: {
            en: {
                common: commonEn,
                builder: builderEn
            }
        },
        lng: 'en',
        fallbackLng: 'en',
        ns: ['common', 'builder'],
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
