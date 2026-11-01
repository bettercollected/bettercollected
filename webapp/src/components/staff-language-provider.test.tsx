import React from 'react';

import { act, fireEvent, render, screen, within } from '@testing-library/react';
import i18n from 'i18next';
import { useTranslation } from 'react-i18next';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import StaffLanguageSwitch from '@app/components/auth/staff-language-switch';
import I18nProvider from '@app/shared/hocs/i18n-provider';
import { axeViolations } from '@app/test/axe';
import { STAFF_LANGUAGE_STORAGE_KEY } from '@app/lib/staff-language';

import { StaffLanguageProvider } from './staff-language-provider';

// a piece of dashboard text and the switch, as the account menu has them
const Probe = () => {
    const { t } = useTranslation();
    return <p data-testid="probe">{t('RESPONSES_LIST.SORT')}</p>;
};
const tree = () => (
    <I18nProvider>
        <StaffLanguageProvider>
            <Probe />
            <ul>
                <StaffLanguageSwitch />
            </ul>
        </StaffLanguageProvider>
    </I18nProvider>
);

const browserSays = (...languages: string[]) => {
    vi.spyOn(window.navigator, 'languages', 'get').mockReturnValue(languages);
    vi.spyOn(window.navigator, 'language', 'get').mockReturnValue(languages[0] ?? 'en');
};

beforeEach(async () => {
    // i18next finishes its own start-up on a timer: wait for it before the first render
    await i18n.changeLanguage('en');
    window.localStorage.clear();
    document.documentElement.lang = 'en';
});
afterEach(async () => {
    vi.restoreAllMocks();
    await i18n.changeLanguage('en');
});

describe('the staff dashboard language', () => {
    it('is Dutch for a Dutch browser, and <html lang> follows', () => {
        browserSays('nl-NL', 'en');
        render(tree());
        expect(screen.getByTestId('probe')).toHaveTextContent('Sorteren op');
        expect(document.documentElement.lang).toBe('nl');
        expect(within(screen.getByRole('radiogroup', { name: 'Taal' })).getByRole('radio', { name: 'Nederlands' })).toBeChecked();
    });

    it('is English for any other browser', () => {
        browserSays('de-DE', 'fr');
        render(tree());
        expect(screen.getByTestId('probe')).toHaveTextContent('Sort by');
        expect(document.documentElement.lang).toBe('en');
        expect(screen.getByRole('radio', { name: 'English' })).toBeChecked();
    });

    it('switches, remembers the choice in this browser and keeps it over the browser\'s language', () => {
        browserSays('nl-NL');
        const { unmount } = render(tree());
        fireEvent.click(screen.getByRole('radio', { name: 'English' }));
        expect(screen.getByTestId('probe')).toHaveTextContent('Sort by');
        expect(document.documentElement.lang).toBe('en');
        expect(window.localStorage.getItem(STAFF_LANGUAGE_STORAGE_KEY)).toBe('en');
        unmount();
        // a new visit: the choice, not the Dutch browser
        render(tree());
        expect(screen.getByTestId('probe')).toHaveTextContent('Sort by');
        fireEvent.click(screen.getByRole('radio', { name: 'Nederlands' }));
        expect(screen.getByTestId('probe')).toHaveTextContent('Sorteren op');
        expect(window.localStorage.getItem(STAFF_LANGUAGE_STORAGE_KEY)).toBe('nl');
        expect(screen.getByRole('radiogroup', { name: 'Taal' })).toBeInTheDocument();
    });

    it('is one tab stop (the checked radio) and moves with the arrow keys, Home and End, as a radio group does', () => {
        browserSays('en');
        render(tree());
        const english = screen.getByRole('radio', { name: 'English' });
        const dutch = screen.getByRole('radio', { name: 'Nederlands' });
        expect(english).toHaveAttribute('tabindex', '0');
        expect(dutch).toHaveAttribute('tabindex', '-1');
        english.focus();
        fireEvent.keyDown(english, { key: 'ArrowRight' });
        expect(dutch).toBeChecked();
        expect(dutch).toHaveFocus();
        expect(dutch).toHaveAttribute('tabindex', '0');
        expect(english).toHaveAttribute('tabindex', '-1');
        expect(screen.getByTestId('probe')).toHaveTextContent('Sorteren op');
        expect(document.documentElement.lang).toBe('nl');
        // the ends wrap
        fireEvent.keyDown(dutch, { key: 'ArrowDown' });
        expect(english).toBeChecked();
        expect(english).toHaveFocus();
        fireEvent.keyDown(english, { key: 'ArrowLeft' });
        expect(dutch).toBeChecked();
        fireEvent.keyDown(dutch, { key: 'Home' });
        expect(english).toBeChecked();
        expect(english).toHaveFocus();
        fireEvent.keyDown(english, { key: 'End' });
        expect(dutch).toBeChecked();
        fireEvent.keyDown(dutch, { key: 'ArrowUp' });
        expect(english).toBeChecked();
        // other keys leave it alone
        fireEvent.keyDown(english, { key: 'a' });
        expect(english).toBeChecked();
    });

    it('names each language in itself and marks it, so it can be found from the other one', () => {
        browserSays('en');
        render(tree());
        expect(screen.getByRole('radio', { name: 'Nederlands' })).toHaveAttribute('lang', 'nl');
        expect(screen.getByRole('radio', { name: 'English' })).toHaveAttribute('lang', 'en');
    });

    it('ignores a stored value that is not a language', () => {
        window.localStorage.setItem(STAFF_LANGUAGE_STORAGE_KEY, 'klingon');
        browserSays('nl');
        render(tree());
        expect(screen.getByTestId('probe')).toHaveTextContent('Sorteren op');
    });

    it('works when storage is blocked: the choice holds for the visit', () => {
        browserSays('en');
        vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
            throw new Error('blocked');
        });
        vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
            throw new Error('blocked');
        });
        render(tree());
        fireEvent.click(screen.getByRole('radio', { name: 'Nederlands' }));
        expect(screen.getByTestId('probe')).toHaveTextContent('Sorteren op');
        expect(document.documentElement.lang).toBe('nl');
    });

    it('follows a choice made in another tab', () => {
        browserSays('en');
        render(tree());
        window.localStorage.setItem(STAFF_LANGUAGE_STORAGE_KEY, 'nl');
        act(() => {
            window.dispatchEvent(new StorageEvent('storage', { key: STAFF_LANGUAGE_STORAGE_KEY, newValue: 'nl' }));
        });
        expect(screen.getByTestId('probe')).toHaveTextContent('Sorteren op');
        expect(document.documentElement.lang).toBe('nl');
    });

    it('puts English back when the dashboard is left, so respondent pages never inherit Dutch', () => {
        browserSays('nl-NL');
        const { unmount } = render(tree());
        expect(i18n.language).toBe('nl');
        unmount();
        expect(i18n.language).toBe('en');
        expect(document.documentElement.lang).toBe('en');
    });

    it('is not offered outside the dashboard (no provider, no switch)', () => {
        render(
            <I18nProvider>
                <ul>
                    <StaffLanguageSwitch />
                </ul>
            </I18nProvider>
        );
        expect(screen.queryByRole('radiogroup')).toBeNull();
    });

    it('has no WCAG A/AA violations, in either language', async () => {
        browserSays('en');
        const { container } = render(tree());
        expect(await axeViolations(container)).toEqual([]);
        fireEvent.click(screen.getByRole('radio', { name: 'Nederlands' }));
        expect(await axeViolations(container)).toEqual([]);
    });
});
