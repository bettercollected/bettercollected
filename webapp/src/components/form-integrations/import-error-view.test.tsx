// The "authorize Google" view only offers the connection while Google Forms
// imports are on; in readonly and off the backend refuses it, so the view says
// why instead.
import React from 'react';

import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import ImportErrorView from './import-error-view';

vi.mock('@app/components/modal-views/context', () => ({ useModal: () => ({ closeModal: vi.fn() }) }));

const providers: { data: any; isLoading: boolean } = { data: undefined, isLoading: false };
vi.mock('@app/store/redux/import-api', async (importOriginal) => ({
    ...((await importOriginal()) as object),
    useGetProvidersQuery: () => providers
}));

describe('ImportErrorView and the Google Forms import switch', () => {
    beforeEach(() => {
        providers.data = undefined;
        providers.isLoading = false;
    });

    it('offers the Google connection while imports are on', () => {
        providers.data = [{ providerName: 'google', importMode: 'on' }];
        render(<ImportErrorView provider="google" />);
        expect(screen.getByText('Authorize Google')).toBeTruthy();
        expect(screen.queryByRole('note')).toBeNull();
    });

    it('offers it as before while the mode is unknown', () => {
        render(<ImportErrorView provider="google" />);
        expect(screen.getByText('Authorize Google')).toBeTruthy();
    });

    it('says imports are read-only instead of offering the connection', () => {
        providers.data = [{ providerName: 'google', importMode: 'readonly' }];
        render(<ImportErrorView provider="google" />);
        expect(screen.queryByText('Authorize Google')).toBeNull();
        expect(screen.getByRole('note').textContent).toContain('GOOGLE_FORMS_IMPORT.READONLY.TITLE');
    });

    it('says Google Forms is off instead of offering the connection', () => {
        providers.data = [];
        render(<ImportErrorView provider="google" closable={false} />);
        expect(screen.queryByText('Authorize Google')).toBeNull();
        expect(screen.getByRole('note').textContent).toContain('GOOGLE_FORMS_IMPORT.OFF.TITLE');
    });

    it('can be closed in readonly and off even where the authorize view is not closable', () => {
        providers.data = [{ providerName: 'google', importMode: 'readonly' }];
        const { container, rerender } = render(<ImportErrorView provider="google" closable={false} />);
        expect(container.querySelector('svg')).toBeTruthy();
        providers.data = [];
        rerender(<ImportErrorView provider="google" closable={false} />);
        expect(container.querySelector('svg')).toBeTruthy();
    });
});
