// The workspace Themes page never saves a theme whose colours fail AA.
import { fireEvent, render, screen } from '@testing-library/react';
import { Provider as ReduxProvider } from 'react-redux';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import '@app/shared/hocs/i18n-provider';
import { store } from '@app/store/store';
import { setWorkspace } from '@app/store/workspaces/slice';

import ThemesPage from './page';

const patch = vi.fn();
vi.mock('@app/store/workspaces/api', async (original) => ({ ...(await original<object>()), usePatchWorkspaceThemesMutation: () => [patch, { isLoading: false }] }));
vi.mock('@app/lib/hooks/use-workspace-permissions', () => ({ useWorkspacePermissions: () => ({ can: () => true }) }));
vi.mock('@app/components/modal-views/context', () => ({ useModal: () => ({ openModal: vi.fn() }) }));

const PASTEL = { title: 'Pastel', primary: '#9CA3AF', secondary: '#1649E2', tertiary: '#818CA0', accent: '#FFFFFF' };

beforeEach(() => {
    patch.mockReset();
    patch.mockResolvedValue({ data: { id: 'w1', customThemes: [] } });
    store.dispatch(setWorkspace({ id: 'w1', workspaceName: 'acme', customThemes: [PASTEL] } as any));
});

const renderPage = () =>
    render(
        <ReduxProvider store={store}>
            <ThemesPage />
        </ReduxProvider>
    );

describe('the Themes page', () => {
    it('flags a saved theme that is hard to read', () => {
        renderPage();
        expect(screen.getByText('Hard to read')).toBeInTheDocument();
    });

    it('refuses to save a failing theme, says why, and saves once the fix is applied', async () => {
        renderPage();
        fireEvent.click(screen.getByRole('button', { name: 'Edit Pastel' }));
        fireEvent.click(screen.getByRole('button', { name: 'Save changes' }));
        expect(patch).not.toHaveBeenCalled();
        expect(screen.getByRole('alert')).toHaveTextContent("This theme can't be saved yet");
        expect(document.activeElement).toBe(screen.getByTestId('contrast-guard'));

        fireEvent.click(screen.getByRole('button', { name: 'Use the suggested colours' }));
        expect(screen.queryByRole('alert')).not.toBeInTheDocument();
        fireEvent.click(screen.getByRole('button', { name: 'Save changes' }));
        await vi.waitFor(() => expect(patch).toHaveBeenCalledTimes(1));
        const saved = patch.mock.calls[0][0].body[0];
        expect(saved.title).toBe('Pastel');
        expect(saved.primary).not.toBe(PASTEL.primary);
    });
});
