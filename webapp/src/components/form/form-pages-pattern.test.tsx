// The page pattern of a form's pages on the canvas of the form shell (components/form/form-page.tsx): Share and every
// Settings page sit in one 760 px column, and what was laid out for a white page (text, inputs, radio rows, rows with
// toggles) sits on surface cards with the strong hairline edge, never straight on the canvas.
import React from 'react';

import { render, screen } from '@testing-library/react';
import { Provider as ReduxProvider } from 'react-redux';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import '@app/shared/hocs/i18n-provider';
import { selectForm, setForm } from '@app/store/forms/slice';
import { store } from '@app/store/store';
import { setWorkspace } from '@app/store/workspaces/slice';

import { FORM_CARD, FORM_ROWS, FormPage } from './form-page';
import FormLinks from './links';
import FormSettingsPage from './settings';
import { settingsPages } from './settings-pages';

vi.mock('@app/lib/hooks/use-workspace-permissions', () => ({
    useWorkspacePermissions: () => ({ can: () => true, saveDraftsEnabled: true, isLoading: false })
}));
vi.mock('@app/store/workspaces/api', async (original) => ({ ...((await original()) as object), usePatchFormSettingsMutation: () => [vi.fn()] }));
vi.mock('@app/components/modal-views/context', () => ({ useModal: () => ({ openModal: vi.fn(), closeModal: vi.fn() }) }));
vi.mock('@app/components/modal-views/full-screen-modal-context', () => ({ useFullScreenModal: () => ({}) }));
vi.mock('@Components/modals/contexts/bottom-sheet-modal-context', () => ({ useBottomSheetModal: () => ({ openBottomSheetModal: vi.fn() }) }));
vi.mock('@app/components/form/automations/automations-section', () => ({ default: () => <section aria-label="Automations" /> }));

const setup = () => {
    window.PUBLIC_CONFIG = { HTTP_SCHEME: 'http://', FORM_DOMAIN: 'localhost:3000' } as any;
    store.dispatch(setWorkspace({ id: 'ws-1', workspaceName: 'acme', isPro: true } as any));
    store.dispatch(setForm({ formId: 'f1', builderVersion: 'v2', title: 'Survey', fields: [], isPublished: true, responses: 3, settings: { provider: 'self', requireVerifiedIdentity: true } } as any));
};

describe('the form page pattern', () => {
    beforeEach(setup);

    it('is a surface with the strong hairline edge and 16 px inside on a phone, 24 px from sm up; rows are divided by the hairline', () => {
        for (const name of ['rounded-lg', 'border', 'border-hairline-strong', 'bg-surface', 'p-4', 'sm:p-6']) expect(FORM_CARD.split(' ')).toContain(name);
        for (const name of ['border-hairline-strong', 'bg-surface', 'divide-y', 'divide-hairline-strong', 'px-4', 'sm:px-6']) expect(FORM_ROWS.split(' ')).toContain(name);
        // semantic utilities only: no hex, no ramp step
        for (const classes of [FORM_CARD, FORM_ROWS]) expect(classes).not.toMatch(/#[0-9a-f]{3,6}|\b(black|brand)-\d/i);
    });

    it('is one column of at most 760 px that may shrink (nothing makes a phone scroll sideways)', () => {
        const { container } = render(<FormPage>content</FormPage>);
        const page = container.firstElementChild as HTMLElement;
        expect(page).toHaveClass('max-w-[760px]', 'min-w-0', 'w-full');
    });

    it('holds every Settings page the form has in that column, with their rows on surface cards and no divider in the old ramp colour', () => {
        const form = selectForm(store.getState());
        const pages = settingsPages(form, (() => true) as any);
        const { container } = render(
            <ReduxProvider store={store}>
                {pages.map((page) => (
                    <FormSettingsPage key={page} page={page} />
                ))}
            </ReduxProvider>
        );
        expect(container.querySelectorAll('.max-w-\\[760px\\]')).toHaveLength(pages.length);
        const lists = container.querySelectorAll('.divide-y');
        expect(lists.length).toBeGreaterThan(0);
        for (const list of lists) {
            expect(list, 'a list of rows').toHaveClass('bg-surface', 'border-hairline-strong', 'divide-hairline-strong');
            expect(list.className).not.toContain('divide-black-300');
        }
    });

    it('puts the Share page (heading, link, slug and the default link) on one card in the same column', () => {
        const { container } = render(
            <ReduxProvider store={store}>
                <FormLinks />
            </ReduxProvider>
        );
        expect(container.firstElementChild).toHaveClass('max-w-[760px]');
        const card = container.querySelector('.bg-surface.border-hairline-strong');
        expect(card).not.toBeNull();
        expect(card).toHaveClass('p-4', 'sm:p-6');
        // the link and its buttons are inside it, not beside it on the canvas
        expect(card).toContainElement(screen.getByRole('button', { name: /copy link/i }));
        expect(screen.getByText('Form Link')).toBeInTheDocument();
    });
});
