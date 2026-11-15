import React from 'react';

import { fireEvent, render, screen } from '@testing-library/react';
import i18n from 'i18next';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { setAuth } from '@app/store/auth/slice';
import { store } from '@app/store/store';

import OnboardingClient from './onbaording-client';

vi.mock('@app/components/ui/logo', () => ({ default: () => <span>logo</span> }));
vi.mock('@app/containers/onboarding', () => ({ default: () => <p>workspace form</p> }));

const renderClient = () => {
    store.dispatch(setAuth({ id: 'u1', email: 'dora@voorbeeld.example', firstName: 'Dora' }));
    return render(
        <ReduxProvider store={store}>
            <OnboardingClient workspace={{ id: 'w1', workspaceName: 'w1', title: '' } as any} />
        </ReduxProvider>
    );
};

afterEach(async () => {
    await i18n.changeLanguage('en');
});

describe('the first run of a new workspace', () => {
    it('writes the brand as bettercollected, lower case, and greets by name in English', () => {
        renderClient();
        expect(screen.getByText('Welcome to bettercollected.')).toBeInTheDocument();
        expect(document.body.textContent).not.toMatch(/betterCollected/);
        expect(screen.queryByText(/^Hey/)).toBeNull();
    });

    it('says the same in Dutch: the brand in lower case, "Welkom, Dora" and the button "Maak uw werkruimte aan"', async () => {
        await i18n.changeLanguage('nl');
        renderClient();
        expect(screen.getByRole('heading', { level: 1, name: 'Welkom, Dora' })).toBeInTheDocument();
        expect(screen.getByText('Welkom bij bettercollected.')).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Maak uw werkruimte aan' })).toBeInTheDocument();
        expect(document.body.textContent).not.toMatch(/betterCollected|Voeg uw organisatie toe|Hoi/);
    });

    it('greets by the email address when there is no first name', () => {
        store.dispatch(setAuth({ id: 'u2', email: 'dora@voorbeeld.example', firstName: '' }));
        render(
            <ReduxProvider store={store}>
                <OnboardingClient workspace={{ id: 'w1', workspaceName: 'w1', title: '' } as any} />
            </ReduxProvider>
        );
        expect(screen.getByRole('heading', { level: 1, name: 'Welcome, dora@voorbeeld.example' })).toBeInTheDocument();
    });

    it("welcomes the creator on the empty states' card: the one heading, one sentence, one next step, the motif once", () => {
        const { container } = renderClient();
        expect(screen.getByRole('heading', { level: 1, name: 'Welcome, Dora' })).toBeInTheDocument();
        expect(screen.getAllByRole('heading')).toHaveLength(1);
        const card = screen.getByTestId('empty-state');
        expect(card).toHaveAttribute('data-illustration', 'true');
        expect(card).toContainElement(screen.getByRole('button', { name: 'Create your workspace' }));
        expect(container.querySelectorAll('svg[viewBox="-360 0 1000 148"]')).toHaveLength(1);
    });

    it('stands on the canvas, not on white', () => {
        const { container } = renderClient();
        expect((container.firstChild as HTMLElement).className).toContain('bg-canvas');
        expect((container.firstChild as HTMLElement).className).not.toContain('bg-white');
    });

    it('goes on to the workspace form on the one button, and the welcome is gone', () => {
        renderClient();
        fireEvent.click(screen.getByRole('button', { name: 'Create your workspace' }));
        expect(screen.getByText('workspace form')).toBeInTheDocument();
        expect(screen.queryByRole('heading', { name: 'Welcome, Dora' })).toBeNull();
    });
});
