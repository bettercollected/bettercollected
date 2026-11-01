'use client';

import { createContext, useCallback, useContext, useEffect, useLayoutEffect, useMemo, useState } from 'react';

import i18n from 'i18next';

import { STAFF_LANGUAGE_STORAGE_KEY, StaffLanguage, browserLanguages, pickStaffLanguage, readChosenStaffLanguage, storeChosenStaffLanguage } from '@app/lib/staff-language';

interface StaffLanguageContextValue {
    language: StaffLanguage;
    setLanguage: (language: StaffLanguage) => void;
}

const StaffLanguageContext = createContext<StaffLanguageContextValue | null>(null);

// useLayoutEffect warns while rendering on the server; the server has no language to apply anyway
const useIsomorphicLayoutEffect = typeof window !== 'undefined' ? useLayoutEffect : useEffect;

/** The staff language and its setter, or null outside the dashboard (the switch is only offered there). */
export function useStaffLanguage() {
    return useContext(StaffLanguageContext);
}

/**
 * Gives the staff dashboard its language: the person's own choice (kept in this
 * browser), else the browser's (Dutch for any nl), else English. It sets
 * i18next's language and `<html lang>`, and puts both back to English when the
 * dashboard is left, so respondent pages never inherit it.
 *
 * The server renders English (it does not know the browser's language, and the
 * i18next instance is shared by every request, so it is never changed there);
 * the language is applied in a layout effect, before the hydrated page is first
 * painted, so there is no second paint in the wrong language.
 */
// (the global i18next instance, like I18nProvider: react-i18next's hook may hand out a different object after a
// language change, which would re-run the effect below)
export function StaffLanguageProvider({ children }: { children: React.ReactNode }) {
    const [language, setLanguageState] = useState<StaffLanguage>('en');

    const apply = useCallback(
        (next: StaffLanguage) => {
            setLanguageState(next);
            if (i18n.language !== next) void i18n.changeLanguage(next);
            document.documentElement.lang = next;
        },
        []
    );

    useIsomorphicLayoutEffect(() => {
        apply(pickStaffLanguage(readChosenStaffLanguage(), browserLanguages()));
        // another tab of this browser chose a language: follow it
        const onStorage = (event: StorageEvent) => {
            if (event.key === STAFF_LANGUAGE_STORAGE_KEY) apply(pickStaffLanguage(readChosenStaffLanguage(), browserLanguages()));
        };
        window.addEventListener('storage', onStorage);
        return () => {
            window.removeEventListener('storage', onStorage);
            // leaving the dashboard: the rest of the app is English again
            void i18n.changeLanguage('en');
            document.documentElement.lang = 'en';
        };
    }, [apply]);

    const setLanguage = useCallback(
        (next: StaffLanguage) => {
            storeChosenStaffLanguage(next);
            apply(next);
        },
        [apply]
    );

    const value = useMemo(() => ({ language, setLanguage }), [language, setLanguage]);
    return <StaffLanguageContext.Provider value={value}>{children}</StaffLanguageContext.Provider>;
}
