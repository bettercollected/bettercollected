import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import enRespondent from '../../../public/locales/en/respondent.json';
import nlRespondent from '../../../public/locales/nl/respondent.json';
import I18nProvider from '@app/shared/hocs/i18n-provider';

import SiretoFooter from './sireto-footer';

describe('Sireto footer', () => {
    it('names the maker, links it to sireto.com, and carries the trademark notice', () => {
        render(<SiretoFooter />, { wrapper: I18nProvider });
        const link = screen.getByRole('link', { name: 'A product of Sireto B.V.' });
        expect(link.getAttribute('href')).toBe('https://sireto.com');
        expect(link.getAttribute('rel')).toContain('noopener');
        // A link in running text is marked by more than colour (WCAG 1.4.1).
        expect(link.className).toMatch(/(^|\s)underline(\s|$)/);
        expect(screen.getByText('Sireto® is a registered trademark of Sireto B.V.')).toBeTruthy();
        expect(screen.getByRole('contentinfo')).toBeTruthy();
        // In the app's language, which the page already declares.
        expect(screen.getByRole('contentinfo').hasAttribute('lang')).toBe(false);
    });

    it("is in the respondent's language where the page is, and says so", () => {
        render(<SiretoFooter language="nl" />, { wrapper: I18nProvider });
        expect(screen.getByRole('link', { name: 'Een product van Sireto B.V.' })).toBeTruthy();
        expect(screen.getByText('Sireto® is een geregistreerd handelsmerk van Sireto B.V.')).toBeTruthy();
        expect(screen.getByRole('contentinfo').getAttribute('lang')).toBe('nl');
    });

    it('is translated for Dutch', () => {
        expect(enRespondent.SIRETO_FOOTER).toEqual({ PRODUCT_OF: 'A product of Sireto B.V.', TRADEMARK: 'Sireto® is a registered trademark of Sireto B.V.' });
        expect(nlRespondent.SIRETO_FOOTER).toEqual({ PRODUCT_OF: 'Een product van Sireto B.V.', TRADEMARK: 'Sireto® is een geregistreerd handelsmerk van Sireto B.V.' });
    });
});
