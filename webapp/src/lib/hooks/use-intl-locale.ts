import { useTranslation } from 'react-i18next';

/** The `Intl` locale for a staff language: Dutch dates and numbers in Dutch, everything else as in the UK. */
export const intlLocaleFor = (language: string | undefined): string => (language?.startsWith('nl') ? 'nl-NL' : 'en-GB');

/** `Intl` locale of the language the dashboard is shown in right now. */
export function useIntlLocale(): string {
    const { i18n } = useTranslation();
    return intlLocaleFor(i18n.language);
}
