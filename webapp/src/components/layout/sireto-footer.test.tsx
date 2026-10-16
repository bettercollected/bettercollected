import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import enCommon from '../../../public/locales/en/common.json';
import nlCommon from '../../../public/locales/nl/common.json';
import I18nProvider from '@app/shared/hocs/i18n-provider';

import SiretoFooter from './sireto-footer';

describe('Sireto footer', () => {
    it('names the maker, links it to sireto.com, and carries the trademark notice', () => {
        render(<SiretoFooter />, { wrapper: I18nProvider });
        const link = screen.getByRole('link', { name: 'A product of Sireto B.V.' });
        expect(link.getAttribute('href')).toBe('https://sireto.com');
        expect(link.getAttribute('rel')).toContain('noopener');
        expect(screen.getByText('Sireto® is a registered trademark of Sireto B.V.')).toBeTruthy();
        expect(screen.getByRole('contentinfo')).toBeTruthy();
    });

    it('is translated for Dutch', () => {
        expect(enCommon.SIRETO_FOOTER).toEqual({ PRODUCT_OF: 'A product of Sireto B.V.', TRADEMARK: 'Sireto® is a registered trademark of Sireto B.V.' });
        expect(nlCommon.SIRETO_FOOTER).toEqual({ PRODUCT_OF: 'Een product van Sireto B.V.', TRADEMARK: 'Sireto® is een geregistreerd handelsmerk van Sireto B.V.' });
    });
});
