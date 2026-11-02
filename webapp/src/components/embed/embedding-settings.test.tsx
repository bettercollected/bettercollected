import React from 'react';

import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import i18n from 'i18next';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import enCommon from '@app/../public/locales/en/common.json';
import nlCommon from '@app/../public/locales/nl/common.json';
import { WorkspacePermission } from '@app/models/enums/workspace-permission';
import '@app/shared/hocs/i18n-provider';
import { axeViolations } from '@app/test/axe';

import EmbeddingSettings from './embedding-settings';

const en = enCommon.STAFF.EMBED as any;

const perms = { ready: true, admin: true, enabled: true };
vi.mock('@app/lib/hooks/use-workspace-permissions', () => ({
    useWorkspacePermissions: () => ({ ready: perms.ready, can: (p: string) => perms.admin && p === 'workspace.manage', formEmbedEnabled: perms.enabled })
}));
vi.mock('@app/store/hooks', () => ({ useAppSelector: () => ({ id: 'ws1', workspaceName: 'acme' }) }));
vi.mock('@app/store/workspaces/slice', () => ({ selectWorkspace: () => ({}) }));

const settings: { data: any; isLoading: boolean; isError: boolean } = { data: { origins: [], canManage: true, maxOrigins: 20 }, isLoading: false, isError: false };
const update = vi.fn();
vi.mock('@app/store/workspaces/embed-api', () => ({
    useGetEmbedSettingsQuery: () => settings,
    useUpdateEmbedSettingsMutation: () => [update, { isLoading: false }]
}));

beforeEach(async () => {
    await i18n.changeLanguage('en');
    perms.ready = true;
    perms.admin = true;
    perms.enabled = true;
    settings.data = { origins: ['https://www.example.org', 'https://*.shop.example.org'], canManage: true, maxOrigins: 20 };
    settings.isLoading = false;
    settings.isError = false;
    update.mockReset();
    update.mockResolvedValue({ data: {} });
});

describe('Embedding settings', () => {
    it('lists the allowed sites and explains what can be entered and what the other site learns', () => {
        render(<EmbeddingSettings />);
        expect(screen.getByText('https://www.example.org')).toBeInTheDocument();
        expect(screen.getByText('https://*.shop.example.org')).toBeInTheDocument();
        expect(screen.getByText(en.FORMAT_WILDCARD)).toBeInTheDocument();
        expect(screen.getByText(en.LEARNS_TEXT)).toBeInTheDocument();
        expect(screen.getByText(en.COUNT.replace('{{count}}', '2').replace('{{max}}', '20'))).toBeInTheDocument();
    });

    it('says so when no site is allowed yet', () => {
        settings.data = { origins: [], canManage: true, maxOrigins: 20 };
        render(<EmbeddingSettings />);
        expect(screen.getByText(en.NONE)).toBeInTheDocument();
    });

    it('shows only a notice to anyone who may not manage the workspace, and nothing while the switch is off', () => {
        perms.admin = false;
        const view = render(<EmbeddingSettings />);
        expect(screen.getByText(en.ONLY_ADMINS)).toBeInTheDocument();
        expect(screen.queryByLabelText(en.ADD_LABEL)).toBeNull();
        view.unmount();
        perms.admin = true;
        perms.enabled = false;
        render(<EmbeddingSettings />);
        expect(screen.getByText(en.TURNED_OFF)).toBeInTheDocument();
        expect(screen.queryByLabelText(en.ADD_LABEL)).toBeNull();
    });

    it('shows nothing to manage while the permissions are unknown', () => {
        perms.ready = false;
        render(<EmbeddingSettings />);
        expect(screen.getByText(en.LOADING)).toBeInTheDocument();
        expect(screen.queryByLabelText(en.ADD_LABEL)).toBeNull();
    });

    it('adds a site by replacing the whole list, then clears the field and says it is saved', async () => {
        render(<EmbeddingSettings />);
        const field = screen.getByLabelText(en.ADD_LABEL) as HTMLInputElement;
        expect(screen.getByRole('button', { name: en.ADD_BUTTON })).toBeDisabled();
        fireEvent.change(field, { target: { value: '  https://new.example.org  ' } });
        fireEvent.click(screen.getByRole('button', { name: en.ADD_BUTTON }));
        await waitFor(() => expect(update).toHaveBeenCalledWith({ workspaceId: 'ws1', origins: ['https://www.example.org', 'https://*.shop.example.org', 'https://new.example.org'] }));
        await waitFor(() => expect(field.value).toBe(''));
        expect(screen.getByText(en.SAVED)).toBeInTheDocument();
    });

    it('keeps what was typed and says what is wrong when the server refuses', async () => {
        update.mockResolvedValue({ error: { status: 422, data: { code: 'origin_wildcard', index: 2 } } });
        render(<EmbeddingSettings />);
        const field = screen.getByLabelText(en.ADD_LABEL) as HTMLInputElement;
        fireEvent.change(field, { target: { value: 'https://*.com' } });
        fireEvent.click(screen.getByRole('button', { name: en.ADD_BUTTON }));
        const alert = await screen.findByRole('alert');
        expect(alert).toHaveTextContent(en.ERROR.origin_wildcard);
        expect(field.value).toBe('https://*.com');
        expect(field).toHaveAttribute('aria-invalid', 'true');
        expect(field.getAttribute('aria-describedby')).toBe(alert.id);
        // typing again clears the message
        fireEvent.change(field, { target: { value: 'https://ok.example.org' } });
        expect(screen.queryByRole('alert')).toBeNull();
    });

    it('removes a site by name', async () => {
        render(<EmbeddingSettings />);
        fireEvent.click(screen.getByRole('button', { name: en.REMOVE_ARIA.replace('{{site}}', 'https://www.example.org') }));
        await waitFor(() => expect(update).toHaveBeenCalledWith({ workspaceId: 'ws1', origins: ['https://*.shop.example.org'] }));
    });

    it('refuses a further site in the form once the list is full', () => {
        settings.data = { origins: Array.from({ length: 20 }, (_, i) => `https://s${i}.example.org`), canManage: true, maxOrigins: 20 };
        render(<EmbeddingSettings />);
        fireEvent.change(screen.getByLabelText(en.ADD_LABEL), { target: { value: 'https://more.example.org' } });
        expect(screen.getByRole('button', { name: en.ADD_BUTTON })).toBeDisabled();
    });

    it('speaks Dutch', async () => {
        await i18n.changeLanguage('nl');
        render(<EmbeddingSettings />);
        expect(screen.getByText(nlCommon.STAFF.EMBED.PAGE_INTRO)).toBeInTheDocument();
        expect(screen.getByLabelText(nlCommon.STAFF.EMBED.ADD_LABEL)).toBeInTheDocument();
    });

    it('has no accessibility violations', async () => {
        const view = render(<EmbeddingSettings />);
        expect(await axeViolations(view.container)).toEqual([]);
    });
});
