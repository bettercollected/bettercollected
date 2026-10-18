// The respondent pages' <html lang> is the respondent's interface language,
// so screen readers read a Dutch page with Dutch pronunciation.
import React from 'react';

import { act, render } from '@testing-library/react';
import { Provider } from 'jotai';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import CustomDomainFormLayout from '@app/app/(custom-domain)/(no-layout)/forms/[form_id]/layout';
import { formContentLanguage } from '@app/lib/hooks/use-form-content-language';
import useRespondentLanguage from '@app/lib/hooks/use-respondent-language';
import '@app/shared/hocs/i18n-provider';

import RespondentDocumentLanguage from './respondent-document-language';

const visit = (search: string) => window.history.replaceState(null, '', `/forms/f1${search}`);

describe('<html lang> on respondent pages', () => {
    beforeEach(() => document.documentElement.setAttribute('lang', 'en'));
    afterEach(() => {
        window.history.replaceState(null, '', '/');
        document.documentElement.setAttribute('lang', 'en');
    });

    it.each([
        ['?lang=nl', 'nl'],
        ['?lang=en', 'en'],
        ['?lang=NL', 'nl']
    ])('a form page opened with %s is in %s', (search, lang) => {
        visit(search);
        render(
            <Provider>
                <CustomDomainFormLayout>
                    <p>Form</p>
                </CustomDomainFormLayout>
            </Provider>
        );
        expect(document.documentElement).toHaveAttribute('lang', lang);
    });

    it("follows the respondent's language switch", () => {
        visit('?lang=en');
        let setLanguage: ReturnType<typeof useRespondentLanguage>['setLanguage'] = () => undefined;
        const Switch = () => {
            setLanguage = useRespondentLanguage().setLanguage;
            return null;
        };
        render(
            <Provider>
                <RespondentDocumentLanguage />
                <Switch />
            </Provider>
        );
        expect(document.documentElement).toHaveAttribute('lang', 'en');
        act(() => setLanguage('nl'));
        expect(document.documentElement).toHaveAttribute('lang', 'nl');
    });

    it('leaving the respondent page puts the app language back', () => {
        visit('?lang=nl');
        const { unmount } = render(
            <Provider>
                <RespondentDocumentLanguage />
            </Provider>
        );
        expect(document.documentElement).toHaveAttribute('lang', 'nl');
        unmount();
        expect(document.documentElement).toHaveAttribute('lang', 'en');
    });
});

describe('formContentLanguage', () => {
    it.each([
        [undefined, 'en', undefined],
        ['', 'en', undefined],
        ['nl', 'nl', undefined],
        ['nl-NL', 'nl', undefined],
        ['NL', 'nl', undefined],
        ['nl', 'en', 'nl'],
        ['en-GB', 'nl', 'en-GB'],
        ['de', 'en', 'de'],
        ['not a tag', 'en', undefined],
        ['"><script>', 'en', undefined]
    ])('declared %s under a %s interface: %s', (declared, ui, expected) => {
        expect(formContentLanguage(declared, ui)).toBe(expected);
    });
});
