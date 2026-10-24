import React from 'react';

import { fireEvent, render, screen } from '@testing-library/react';
import { Provider as ReduxProvider } from 'react-redux';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { store } from '@app/store/store';

import ImportFormModal from './import-form-modal';

vi.mock('next/navigation', () => ({ useRouter: () => ({ push: vi.fn() }) }));
vi.mock('@fyelci/react-google-drive-picker', () => ({ default: () => [vi.fn()] }));
const closeModal = vi.fn();
vi.mock('@app/components/modal-views/context', () => ({ useModal: () => ({ closeModal, openModal: vi.fn() }) }));
vi.mock('@app/components/form-integrations/import-error-view', () => ({ default: () => <p>authorize google</p> }));
vi.mock('@app/components/ui/fullscreen-loader', () => ({ default: () => <p>loading</p> }));

const providers: { data: any; isLoading: boolean } = { data: undefined, isLoading: false };
const verify: { fn: ReturnType<typeof vi.fn>; state: any } = { fn: vi.fn(), state: {} };
vi.mock('@app/store/redux/import-api', async (importOriginal) => {
    const actual: any = await importOriginal();
    return {
        ...actual,
        useGetProvidersQuery: () => providers,
        useVerifyFormTokenMutation: () => [verify.fn, verify.state],
        useImportFormMutation: () => [vi.fn(), {}],
        useLazyGetSingleFormFromProviderQuery: () => [vi.fn(), {}]
    };
});

const renderModal = () =>
    render(
        <ReduxProvider store={store}>
            <ImportFormModal />
        </ReduxProvider>
    );

describe('ImportFormModal and the Google Forms import switch', () => {
    beforeEach(() => {
        verify.fn = vi.fn();
        verify.state = {};
        providers.isLoading = false;
        closeModal.mockReset();
    });

    it('says imports are read-only and asks nothing of Google', () => {
        providers.data = [{ providerName: 'google', importMode: 'readonly' }];
        renderModal();

        expect(screen.getByRole('note').textContent).toContain('GOOGLE_FORMS_IMPORT.READONLY.TITLE');
        expect(verify.fn).not.toHaveBeenCalled();
        fireEvent.click(screen.getByRole('button', { name: 'BUTTON.CLOSE' }));
        expect(closeModal).toHaveBeenCalled();
    });

    it('says imports are off when Google is not offered', () => {
        providers.data = [];
        renderModal();

        expect(screen.getByRole('note').textContent).toContain('GOOGLE_FORMS_IMPORT.OFF.TITLE');
        expect(verify.fn).not.toHaveBeenCalled();
    });

    it('connects to Google while imports are on', () => {
        providers.data = [{ providerName: 'google', importMode: 'on' }];
        renderModal();

        expect(verify.fn).toHaveBeenCalledWith({ provider: 'google' });
        expect(screen.queryByRole('note')).toBeNull();
    });

    it("explains the backend's refusal instead of asking to authorize Google", () => {
        providers.data = undefined; // the provider list could not be read
        verify.state = { error: { status: 403, data: { code: 'google_forms_readonly' } } };
        renderModal();

        expect(screen.getByRole('note').textContent).toContain('GOOGLE_FORMS_IMPORT.READONLY.DESCRIPTION');
        expect(screen.queryByText('authorize google')).toBeNull();

        verify.state = { error: { status: 410, data: { code: 'google_forms_off' } } };
        renderModal();
        expect(screen.getAllByRole('note')[1].textContent).toContain('GOOGLE_FORMS_IMPORT.OFF.DESCRIPTION');
    });

    it('still asks to authorize Google after any other error', () => {
        providers.data = [{ providerName: 'google', importMode: 'on' }];
        verify.state = { error: { status: 401, data: { unauthorizedScopes: [] } } };
        renderModal();

        expect(screen.getByText('authorize google')).toBeTruthy();
    });
});
