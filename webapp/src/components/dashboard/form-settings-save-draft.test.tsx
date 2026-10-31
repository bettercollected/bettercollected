// The "Let respondents save and continue later" row of a form's settings:
// editable while the server has the feature on, read-only (with the reason)
// while SAVE_DRAFTS_ENABLED is off. English and Dutch.
import React from 'react';

import { readFileSync } from 'fs';
import { resolve } from 'path';

import { act, fireEvent, render, screen } from '@testing-library/react';
import { Provider as ReduxProvider } from 'react-redux';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import '@app/shared/hocs/i18n-provider';
import { setForm } from '@app/store/forms/slice';
import { store } from '@app/store/store';
import { setWorkspace } from '@app/store/workspaces/slice';
import { axeViolations } from '@app/test/axe';

import FormSettingsTab from './form-settings';

const served = vi.hoisted(() => ({ saveDraftsEnabled: true }));
vi.mock('@app/lib/hooks/use-workspace-permissions', () => ({ useWorkspacePermissions: () => ({ can: () => true, saveDraftsEnabled: served.saveDraftsEnabled }) }));
const patch = vi.fn();
vi.mock('@app/store/workspaces/api', async (original) => ({ ...((await original()) as object), usePatchFormSettingsMutation: () => [patch] }));
vi.mock('@app/components/modal-views/context', () => ({ useModal: () => ({ openModal: vi.fn(), closeModal: vi.fn() }) }));
vi.mock('@app/components/modal-views/full-screen-modal-context', () => ({ useFullScreenModal: () => ({}) }));
vi.mock('@Components/modals/contexts/bottom-sheet-modal-context', () => ({ useBottomSheetModal: () => ({ openBottomSheetModal: vi.fn() }) }));

const open = (settings: Record<string, unknown>) => {
    store.dispatch(setWorkspace({ id: 'ws-1', workspaceName: 'acme' } as any));
    store.dispatch(setForm({ formId: 'f1', builderVersion: 'v2', title: 'Survey', fields: [], isPublished: false, settings: { provider: 'self', ...settings } } as any));
    return render(
        <ReduxProvider store={store}>
            <FormSettingsTab />
        </ReduxProvider>
    );
};

describe('the save and continue later setting', () => {
    beforeEach(() => {
        window.PUBLIC_CONFIG = { HTTP_SCHEME: 'http://', FORM_DOMAIN: 'localhost:3000' } as any;
        patch.mockReset();
        patch.mockResolvedValue({ data: { settings: { provider: 'self', allowSaveDraft: true } } });
        served.saveDraftsEnabled = true;
    });

    it('turns on and off, with the days field while it is on, when the server has the feature on', async () => {
        open({ allowSaveDraft: false });
        const toggle = screen.getByTestId('save-draft-switch');
        expect(toggle).not.toBeDisabled();
        expect(screen.queryByTestId('save-draft-off-note')).toBeNull();
        expect(screen.queryByTestId('draft-days-input')).toBeNull();
        await act(async () => void fireEvent.click(toggle));
        expect(patch).toHaveBeenCalledWith(expect.objectContaining({ workspaceId: 'ws-1', formId: 'f1', body: { allowSaveDraft: true } }));
    });

    it('shows the days field once it is on', () => {
        open({ allowSaveDraft: true, draftRetentionDays: 14 });
        expect((screen.getByTestId('draft-days-input') as HTMLInputElement).value).toBe('14');
    });

    it('is read-only, and says why, while the server has it switched off', async () => {
        served.saveDraftsEnabled = false;
        open({ allowSaveDraft: false });
        const toggle = screen.getByTestId('save-draft-switch');
        expect(toggle).toBeDisabled();
        expect(screen.getByTestId('save-draft-off-note').textContent).toContain('Saving drafts is not switched on on this server yet, so this setting cannot be turned on.');
        expect(screen.queryByTestId('draft-days-input')).toBeNull();
        await act(async () => void fireEvent.click(toggle));
        expect(patch).not.toHaveBeenCalled();
        expect(await axeViolations(document, { page: false })).toEqual([]);
    });

    it('has its Dutch text (the dashboard bundles English only until it has a language switch)', () => {
        const en = JSON.parse(readFileSync(resolve(__dirname, '../../../public/locales/en/common.json'), 'utf8')).FORM_PAGE.SETTINGS.SAVE_DRAFT;
        const nl = JSON.parse(readFileSync(resolve(__dirname, '../../../public/locales/nl/common.json'), 'utf8')).FORM_PAGE.SETTINGS.SAVE_DRAFT;
        expect(Object.keys(nl).sort()).toEqual(Object.keys(en).sort());
        for (const key of Object.keys(en)) expect(nl[key]).not.toBe(en[key]);
        expect(nl.OFF_NOTE).toBe('Concepten opslaan is op deze server nog niet ingeschakeld, dus deze instelling kan nog niet worden aangezet.');
    });
});
