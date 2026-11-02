// The Settings page in its sections: Access, Availability, Respondent experience,
// the automations and Advanced. Every setting is where the plan puts it, and the
// conditions each setting had are unchanged (apart from the two the owner changed:
// "Allow response editing" is shown disabled without verified identity, and the
// branding row shows for any published form).
import React from 'react';

import { act, fireEvent, render, screen, within } from '@testing-library/react';
import i18n from 'i18next';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';

import '@app/shared/hocs/i18n-provider';
import { setForm } from '@app/store/forms/slice';
import { store } from '@app/store/store';
import { setWorkspace } from '@app/store/workspaces/slice';
import { axeViolations } from '@app/test/axe';

import FormSettings from './settings';

import commonNl from '../../../public/locales/nl/common.json';

const served = vi.hoisted(() => ({ permissions: ['form.edit', 'form.delete'] as string[] }));
vi.mock('@app/lib/hooks/use-workspace-permissions', () => ({
    useWorkspacePermissions: () => ({ can: (permission: string) => served.permissions.includes(permission), saveDraftsEnabled: true, isLoading: false })
}));
const patch = vi.fn();
vi.mock('@app/store/workspaces/api', async (original) => ({ ...((await original()) as object), usePatchFormSettingsMutation: () => [patch] }));
const openModal = vi.fn();
vi.mock('@app/components/modal-views/context', () => ({ useModal: () => ({ openModal, closeModal: vi.fn() }) }));
vi.mock('@app/components/modal-views/full-screen-modal-context', () => ({ useFullScreenModal: () => ({}) }));
vi.mock('@Components/modals/contexts/bottom-sheet-modal-context', () => ({ useBottomSheetModal: () => ({ openBottomSheetModal: vi.fn() }) }));
// The automations are other components with their own tests.
vi.mock('@app/components/form/integrations', () => ({ default: () => <p>integrations</p> }));
vi.mock('@app/components/registration/form-registration-settings', () => ({ default: () => null }));
vi.mock('@app/components/webhooks/webhooks-section', () => ({ default: () => null }));
vi.mock('@app/components/email-actions/email-actions-section', () => ({ default: () => null }));

const open = (settings: Record<string, unknown> = {}, form: Record<string, unknown> = {}, workspace: Record<string, unknown> = {}) => {
    store.dispatch(setWorkspace({ id: 'ws-1', workspaceName: 'acme', isPro: true, ...workspace } as any));
    store.dispatch(setForm({ formId: 'f1', builderVersion: 'v2', title: 'Survey', fields: [], isPublished: true, responses: 3, settings: { provider: 'self', requireVerifiedIdentity: true, ...settings }, ...form } as any));
    return render(
        <ReduxProvider store={store}>
            <FormSettings />
        </ReduxProvider>
    );
};
const section = (name: string) => screen.getByRole('region', { name });

describe('the settings sections', () => {
    beforeAll(() => {
        i18n.addResourceBundle('nl', 'common', commonNl, true, true);
    });

    afterEach(async () => {
        await i18n.changeLanguage('en');
    });

    beforeEach(() => {
        window.PUBLIC_CONFIG = { HTTP_SCHEME: 'http://', FORM_DOMAIN: 'localhost:3000' } as any;
        patch.mockReset();
        patch.mockResolvedValue({ data: { settings: { provider: 'self' } } });
        openModal.mockReset();
        served.permissions = ['form.edit', 'form.delete'];
    });

    it('has Access, Availability, Respondent experience and Advanced, in that order, as h2 sections', () => {
        const { container } = open();
        const headings = Array.from(container.querySelectorAll('h2')).map((h) => h.textContent);
        expect(headings).toEqual(['Access', 'Availability', 'Respondent experience', 'Integrations', 'Advanced']);
        for (const id of ['access', 'availability', 'experience', 'automations', 'advanced']) expect(container.querySelector(`#${id}`)).not.toBeNull();
    });

    it('is Dutch in Dutch, formal', async () => {
        await i18n.changeLanguage('nl');
        const { container } = open({ formCloseDate: '2099-01-01T10:00:00Z' });
        expect(Array.from(container.querySelectorAll('h2')).map((h) => h.textContent)).toEqual(['Toegang', 'Beschikbaarheid', 'Ervaring van respondenten', 'Integraties', 'Geavanceerd']);
        expect(screen.getByTestId('availability-status').textContent).toContain('sluit op');
        expect(screen.getByRole('button', { name: 'Sluitingsdatum verwijderen' })).toBeInTheDocument();
        expect(within(section('Ervaring van respondenten')).getAllByRole('heading', { level: 3 }).map((h) => h.textContent)).toEqual(['Tijdens het invullen', 'Na het verzenden', 'Branding']);
        expect(screen.getByTestId('open-builder-privacy').textContent).toBe('Openen in de bouwer');
    });

    it('puts visibility and verified identity under Access', () => {
        open();
        const access = within(section('Access'));
        expect(access.getByRole('radio', { name: /Public/ })).toBeInTheDocument();
        expect(access.getByTestId('require-verified-identity-switch')).toBeChecked();
        expect(access.queryByTestId('close-form-switch')).toBeNull();
    });

    it('puts the open date, close and the limit under Availability, with the status line first', () => {
        open({ responseLimit: 100 });
        const availability = within(section('Availability'));
        expect(availability.getByTestId('availability-status').textContent).toContain('3 of 100 responses');
        expect(availability.getByTestId('open-date-input')).toBeInTheDocument();
        expect(availability.getByTestId('close-form-switch')).toBeInTheDocument();
        expect(availability.getByTestId('response-limit-input')).toBeInTheDocument();
    });

    it('groups Respondent experience into while filling in, after sending and branding', () => {
        open();
        const experience = within(section('Respondent experience'));
        expect(experience.getAllByRole('heading', { level: 3 }).map((h) => h.textContent)).toEqual(['While filling in', 'After sending', 'Branding']);
        for (const id of ['show-review-page-switch', 'save-draft-switch', 'show-submission-number-switch', 'allow-response-editing-switch', 'respondent-feedback-switch', 'disable-branding-switch']) {
            expect(experience.getByTestId(id)).toBeInTheDocument();
        }
    });

    it('no longer has a Pin form row in the settings', () => {
        open({ pinned: false });
        expect(screen.queryByTestId('pinned-switch')).toBeNull();
        expect(screen.queryByText('Pin Form')).toBeNull();
    });

    it('shows "Allow response editing" disabled, and says why, while verified identity is off', () => {
        open({ requireVerifiedIdentity: false, allowEditingResponse: false });
        const toggle = screen.getByTestId('allow-response-editing-switch');
        expect(toggle).toBeDisabled();
        const hint = screen.getByTestId('editing-needs-identity');
        expect(hint.textContent).toContain('Turn on “Require verified identity” first.');
        expect(within(hint).getByRole('link', { name: 'Go to Access' })).toHaveAttribute('href', '#access');
    });

    it('lets "Allow response editing" be switched while verified identity is on', async () => {
        open({ allowEditingResponse: false });
        const toggle = screen.getByTestId('allow-response-editing-switch');
        expect(toggle).not.toBeDisabled();
        expect(screen.queryByTestId('editing-needs-identity')).toBeNull();
        await act(async () => void fireEvent.click(toggle));
        expect(patch).toHaveBeenCalledWith(expect.objectContaining({ body: { allowEditingResponse: true } }));
    });

    it('shows the branding row for a published form even after it closed, not for a draft', () => {
        const { unmount } = open({ formCloseDate: '2020-01-01T00:00:00Z' });
        expect(screen.getByTestId('disable-branding-switch')).toBeInTheDocument();
        unmount();
        open({}, { isPublished: false });
        expect(screen.queryByTestId('disable-branding-switch')).toBeNull();
    });

    it('locks branding on a free plan, with the Pro note', () => {
        open({}, {}, { isPro: false });
        expect(screen.getByTestId('disable-branding-switch')).toBeDisabled();
        expect(screen.getByText(/Available on Pro/)).toBeInTheDocument();
    });

    it('removes the scheduled close date with a real, named button', async () => {
        open({ formCloseDate: '2099-01-01T10:00:00Z' });
        const remove = screen.getByRole('button', { name: 'Remove the close date' });
        expect(remove.tagName).toBe('BUTTON');
        await act(async () => void fireEvent.click(remove));
        expect(openModal).not.toHaveBeenCalled();
        expect(patch).toHaveBeenCalledWith(expect.objectContaining({ body: { formCloseDate: '' } }));
    });

    it('has the privacy link to the builder and the danger zone under Advanced', () => {
        open();
        const advanced = within(section('Advanced'));
        expect(advanced.getByTestId('open-builder-privacy')).toHaveAttribute('href', '/acme/dashboard/forms/f1/edit?tab=form');
        expect(advanced.getByRole('heading', { level: 3, name: 'Danger zone' })).toBeInTheDocument();
        fireEvent.click(advanced.getByRole('button', { name: 'Delete form' }));
        expect(openModal).toHaveBeenCalledWith('DELETE_FORM_MODAL', expect.objectContaining({ redirectToDashboard: true }));
    });

    it('hides the danger zone without form.delete', () => {
        served.permissions = ['form.edit'];
        open();
        expect(screen.queryByRole('button', { name: 'Delete form' })).toBeNull();
        expect(within(section('Advanced')).getByTestId('open-builder-privacy')).toBeInTheDocument();
    });

    it('shows the original-form switch under Advanced for an imported form, which has no self-only sections', () => {
        open({ provider: 'google', showOriginalForm: false }, { importedFormId: 'g1', builderVersion: 'v1' });
        expect(within(section('Advanced')).getByTestId('show-original-form-switch')).toBeInTheDocument();
        expect(screen.queryByRole('region', { name: 'Availability' })).toBeNull();
        expect(screen.queryByTestId('open-builder-privacy')).toBeNull();
        expect(within(section('Respondent experience')).getByTestId('disable-branding-switch')).toBeInTheDocument();
    });

    it('has no accessibility violations', async () => {
        open({ formCloseDate: '2099-01-01T10:00:00Z', responseLimit: 10 });
        expect(await axeViolations(document, { page: false })).toEqual([]);
    });
});
