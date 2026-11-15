import React from 'react';

import { render, screen } from '@testing-library/react';
import { Provider as ReduxProvider } from 'react-redux';
import { describe, expect, it, vi } from 'vitest';

vi.mock('next/navigation', () => ({ useRouter: () => ({ push: vi.fn() }) }));
vi.mock('react-i18next', () => ({ useTranslation: () => ({ t: (key: string) => key }) }));
vi.mock('@app/components/auth/auth-navbar', () => ({ default: () => <header data-testid="navbar" /> }));

import { invitationConstant } from '@app/constants/locales/invitations';
import { store } from '@app/store/store';

import MainValidUser from './main-valid-user';

// The invitation page sits on the canvas: the top bar runs the full width (the page adds no gutter of its own around it),
// and everything the invitation says, including what the person will have access to, is in one card.
describe('the invitation page', () => {
    const renderPage = () =>
        render(
            <ReduxProvider store={store}>
                <MainValidUser workspace={{ id: 'w', title: 'Stichting Voorbeeld', workspaceName: 'voorbeeld' } as any} user={{ id: 'u' } as any} invitation={{ invitationToken: 't' } as any} />
            </ReduxProvider>
        );

    it('keeps the top bar outside any padded wrapper, so it starts at the left edge', () => {
        const { container } = renderPage();
        const root = container.firstElementChild as HTMLElement;
        expect(root.className).not.toMatch(/\b(absolute|px-\d)\b/);
        expect(screen.getByTestId('navbar').parentElement).toBe(root);
    });

    it('puts the heading, the answers and the access list in the same hairline card', () => {
        renderPage();
        const card = screen.getByText(invitationConstant.list.title).closest('[class*="bg-surface"]') as HTMLElement;
        expect(card).not.toBeNull();
        expect(card.className).toContain('border-hairline-strong');
        expect(card).toContainElement(screen.getByText(invitationConstant.expiryLink));
        expect(card).toContainElement(screen.getByText(invitationConstant.list.item3));
    });
});
