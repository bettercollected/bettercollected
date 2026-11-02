'use client';

import { useEffect, useMemo, useState } from 'react';

import { useTranslation } from 'react-i18next';

import { useStaffLanguage } from '@app/components/staff-language-provider';
import { StaffLanguage, browserLanguages, pickStaffLanguage, readChosenStaffLanguage } from '@app/lib/staff-language';

/**
 * The translator of the second-factor screens. Inside the dashboard it is the
 * dashboard's own (its language is already set). The sign-in page is outside
 * it and always English, but the code step is for a person who may read Dutch:
 * there it follows the person's own choice, else the browser's, as the
 * dashboard will once they are in. `language` is for the element's `lang`.
 */
export function useMfaT() {
    const { t, i18n } = useTranslation();
    const inDashboard = useStaffLanguage() !== null;
    const [chosen, setChosen] = useState<StaffLanguage>('en');
    useEffect(() => {
        if (!inDashboard) setChosen(pickStaffLanguage(readChosenStaffLanguage(), browserLanguages()));
    }, [inDashboard]);
    const language: StaffLanguage = inDashboard ? (i18n.language === 'nl' ? 'nl' : 'en') : chosen;
    const translate = useMemo(() => (inDashboard ? t : i18n.getFixedT(language)), [inDashboard, t, i18n, language]);
    return { t: translate, language };
}
