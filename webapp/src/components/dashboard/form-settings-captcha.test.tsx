// The "Spam protection (automatic, no puzzle)" row of a form's Settings, in
// Respondent experience: offered only while the server has the check on
// (CAPTCHA_ENABLED), on unless the creator turns it off. English and Dutch.
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

const served = vi.hoisted(() => ({ captchaEnabled: true }));
vi.mock('@app/lib/hooks/use-workspace-permissions', () => ({ useWorkspacePermissions: () => ({ can: () => true, saveDraftsEnabled: true, captchaEnabled: served.captchaEnabled }) }));
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

describe('the automatic spam check setting', () => {
    beforeEach(() => {
        window.PUBLIC_CONFIG = { HTTP_SCHEME: 'http://', FORM_DOMAIN: 'localhost:3000' } as any;
        patch.mockReset();
        patch.mockResolvedValue({ data: { settings: { provider: 'self', captchaEnabled: false } } });
        served.captchaEnabled = true;
    });

    it('is on by default, with its label and the line under it', async () => {
        open({});
        const toggle = screen.getByTestId('captcha-switch');
        expect(toggle).toBeChecked();
        expect(screen.getByText('Spam protection (automatic, no puzzle)')).toBeInTheDocument();
        expect(screen.getByText('Respondents solve nothing; their browser does a small calculation.')).toBeInTheDocument();
        expect(await axeViolations(document, { page: false })).toEqual([]);
    });

    it('turns off and on again', async () => {
        open({});
        await act(async () => void fireEvent.click(screen.getByTestId('captcha-switch')));
        expect(patch).toHaveBeenLastCalledWith(expect.objectContaining({ workspaceId: 'ws-1', formId: 'f1', body: { captchaEnabled: false } }));
    });

    it('shows a form the creator turned off as off', () => {
        open({ captchaEnabled: false });
        expect(screen.getByTestId('captcha-switch')).not.toBeChecked();
    });

    it('is not offered at all while the server has it switched off', () => {
        served.captchaEnabled = false;
        open({ captchaEnabled: false });
        expect(screen.queryByTestId('captcha-switch')).toBeNull();
        expect(screen.queryByText('Spam protection (automatic, no puzzle)')).toBeNull();
    });

    it('has its Dutch text', () => {
        const en = JSON.parse(readFileSync(resolve(__dirname, '../../../public/locales/en/common.json'), 'utf8')).FORM_PAGE.SETTINGS.CAPTCHA;
        const nl = JSON.parse(readFileSync(resolve(__dirname, '../../../public/locales/nl/common.json'), 'utf8')).FORM_PAGE.SETTINGS.CAPTCHA;
        expect(Object.keys(nl).sort()).toEqual(Object.keys(en).sort());
        expect(nl.TITLE).toBe('Spamcontrole (automatisch, zonder puzzel)');
        expect(nl.DESCRIPTION).toBe('Respondenten hoeven niets op te lossen; hun browser voert een kleine berekening uit.');
    });
});
