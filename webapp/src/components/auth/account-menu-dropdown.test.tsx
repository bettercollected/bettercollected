import React from 'react';

import { fireEvent, render, screen, within } from '@testing-library/react';
import i18n from 'i18next';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { StaffLanguageProvider } from '@app/components/staff-language-provider';
import I18nProvider from '@app/shared/hocs/i18n-provider';
import { STAFF_LANGUAGE_STORAGE_KEY } from '@app/lib/staff-language';
import { store } from '@app/store/store';
import { setWorkspace } from '@app/store/workspaces/slice';

import AuthAccountMenuDropdown from './account-menu-dropdown';

vi.mock('@app/store/auth/api', async (importOriginal) => {
    const actual: any = await importOriginal();
    return { ...actual, useGetStatusQuery: () => ({ data: { id: 'u1', email: 'owner@example.com', firstName: 'Olga', lastName: 'Owner', isLoading: false } }) };
});
vi.mock('@Components/hocs/workspace-admin-selector', () => ({ default: () => null }));
vi.mock('@app/components/modal-views/context', () => ({ useModal: () => ({ openModal: vi.fn(), closeModal: vi.fn() }) }));

const dashboard = () => (
    <ReduxProvider store={store}>
        <I18nProvider>
            <StaffLanguageProvider>
                <AuthAccountMenuDropdown />
            </StaffLanguageProvider>
        </I18nProvider>
    </ReduxProvider>
);
const outside = () => (
    <ReduxProvider store={store}>
        <I18nProvider>
            <AuthAccountMenuDropdown />
        </I18nProvider>
    </ReduxProvider>
);

beforeEach(async () => {
    await i18n.changeLanguage('en');
    window.localStorage.clear();
    (window as any).PUBLIC_CONFIG = { DASHBOARD_DOMAIN: 'localhost:3000' };
    store.dispatch(setWorkspace({ id: 'w1', workspaceName: 'acme', ownerId: 'u1' } as any));
    vi.spyOn(window.navigator, 'languages', 'get').mockReturnValue(['en-GB']);
});
afterEach(async () => {
    vi.restoreAllMocks();
    await i18n.changeLanguage('en');
});

describe('the account menu\'s language switch', () => {
    it('is in the menu of the dashboard, switches the language and keeps the menu open', () => {
        render(dashboard());
        fireEvent.click(document.getElementById('account-menu')!);
        const menu = screen.getByRole('radiogroup', { name: 'Language' });
        fireEvent.click(within(menu).getByRole('radio', { name: 'Nederlands' }));
        // the menu stays and now speaks Dutch
        expect(screen.getByRole('radiogroup', { name: 'Taal' })).toBeInTheDocument();
        expect(screen.getByRole('radio', { name: 'Nederlands' })).toBeChecked();
        expect(document.documentElement.lang).toBe('nl');
        expect(window.localStorage.getItem(STAFF_LANGUAGE_STORAGE_KEY)).toBe('nl');
    });

    it('is not in the menu outside the dashboard (a client domain\'s account menu)', () => {
        render(outside());
        fireEvent.click(document.getElementById('account-menu')!);
        expect(screen.queryByRole('radiogroup')).toBeNull();
    });
});
