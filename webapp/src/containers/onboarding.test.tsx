import React from 'react';

import { render, screen } from '@testing-library/react';
import { Provider as ReduxProvider } from 'react-redux';
import { describe, expect, it, vi } from 'vitest';

import { setAuth } from '@app/store/auth/slice';
import { store } from '@app/store/store';

import OnboardingContainer from './onboarding';

vi.mock('next/navigation', () => ({ useRouter: () => ({ replace: vi.fn() }) }));
vi.mock('@app/components/auth/auth-navbar', () => ({ default: () => <nav>nav</nav> }));
vi.mock('@Components/common/upload-logo', () => ({ default: () => <p>upload logo</p> }));
vi.mock('@Components/onboarding/workspace-name-input-handler', () => ({ default: () => <p>handle</p> }));

const renderContainer = (createWorkspace = false) => {
    store.dispatch(setAuth({ id: 'u1', email: 'dora@voorbeeld.example', firstName: 'Dora' }));
    return render(
        <ReduxProvider store={store}>
            <OnboardingContainer workspace={{ id: 'w1', workspaceName: 'w1', title: '' } as any} createWorkspace={createWorkspace} />
        </ReduxProvider>
    );
};

describe('the workspace form of the first run', () => {
    it('is one card on the canvas: the motif once, the page heading, then the fields', () => {
        const { container } = renderContainer();
        expect((container.firstChild as HTMLElement).className).toContain('bg-canvas');
        const card = screen.getByRole('region', { name: 'Create your workspace' });
        expect(card).toHaveClass('bg-surface', 'border-hairline-strong');
        expect(screen.getByRole('heading', { level: 1, name: 'Create your workspace' })).toBeInTheDocument();
        expect(container.querySelectorAll('svg[viewBox="-360 0 1000 148"]')).toHaveLength(1);
        expect(card).toContainElement(screen.getByLabelText('Workspace name'));
        expect(card).toContainElement(screen.getByRole('button', { name: 'Add Now' }));
    });

    it('keeps the logic: the button is closed until the name and the handle are there, and the same card serves the create page', () => {
        renderContainer(true);
        expect(screen.getByRole('button', { name: 'Add Now' })).toBeDisabled();
        expect(screen.getByRole('heading', { level: 1 })).toBeInTheDocument();
    });
});
