// The published dialog is announced once: the dialog is named by its visible heading, and no other dialog changes.
import React from 'react';

import { fireEvent, render, screen } from '@testing-library/react';
import { Provider as JotaiProvider } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { describe, expect, it, vi } from 'vitest';

import '@app/shared/hocs/i18n-provider';
import { store } from '@app/store/store';
import { setForm } from '@app/store/forms/slice';
import { setWorkspace } from '@app/store/workspaces/slice';

import { DialogModalContainer, useDialogModal } from './use-dialog-modal';

vi.mock('next/navigation', () => ({ usePathname: () => '/acme/dashboard/forms/f-123/edit' }));

function Opener() {
    const { openDialogModal } = useDialogModal();
    return (
        <button type="button" onClick={() => openDialogModal('FORM_PUBLISHED')}>
            open
        </button>
    );
}

const open = () => {
    (window as any).PUBLIC_CONFIG = { HTTP_SCHEME: 'https://', FORM_DOMAIN: 'forms.example.test', DASHBOARD_DOMAIN: 'admin.example.test' };
    store.dispatch(setWorkspace({ id: 'ws-1', workspaceName: 'acme' } as any));
    store.dispatch(setForm({ formId: 'f-123', builderVersion: 'v2', settings: {} } as any));
    render(
        <JotaiProvider>
            <ReduxProvider store={store}>
                <Opener />
                <DialogModalContainer />
            </ReduxProvider>
        </JotaiProvider>
    );
    fireEvent.click(screen.getByRole('button', { name: 'open' }));
};

describe('the "Your form is live" dialog', () => {
    it('is named by its visible heading, which is announced once', () => {
        open();
        const dialog = screen.getByRole('dialog', { name: 'Your form is live' });
        const heading = screen.getByRole('heading', { name: 'Your form is live' });
        expect(dialog.getAttribute('aria-labelledby')).toBe(heading.id);
        expect(screen.getAllByRole('heading', { name: 'Your form is live' })).toHaveLength(1);
        // the hidden copy of the title is not in the accessibility tree
        const hidden = [...dialog.querySelectorAll('.sr-only')].find((element) => element.textContent === 'Your form is live');
        expect(hidden).toHaveAttribute('aria-hidden', 'true');
    });
});
