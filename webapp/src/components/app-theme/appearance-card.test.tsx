import React from 'react';

import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import '@app/shared/hocs/i18n-provider';
import { WorkspacePermission } from '@app/models/enums/workspace-permission';
import { axeViolations } from '@app/test/axe';

import AppearanceCard, { appThemeErrorKey } from './appearance-card';

const permissions = { can: (_: WorkspacePermission) => true, appThemeEnabled: true };
vi.mock('@app/lib/hooks/use-workspace-permissions', () => ({ useWorkspacePermissions: () => permissions }));
const workspace: { id: string; appTheme?: string } = { id: 'ws-1', appTheme: 'daybreak' };
vi.mock('@app/store/hooks', () => ({ useAppSelector: () => workspace }));
vi.mock('@app/store/workspaces/slice', () => ({ selectWorkspace: () => workspace }));

const save = vi.fn();
const useMutation = vi.fn(() => [save, { isLoading: false }]);
vi.mock('@app/store/workspaces/app-theme-api', () => ({ useSetWorkspaceAppThemeMutation: () => useMutation() }));

beforeEach(() => {
    save.mockReset().mockResolvedValue({ data: { appTheme: 'pigment' } });
    useMutation.mockClear();
    Object.assign(permissions, { can: () => true, appThemeEnabled: true });
    Object.assign(workspace, { id: 'ws-1', appTheme: 'daybreak' });
});

const radio = (name: RegExp) => screen.getByRole('radio', { name });
const saveButton = () => screen.getByRole('button', { name: 'Save appearance' });

describe('the Appearance card', () => {
    it('is a radio group named Appearance with the two themes, the one in use checked and marked', () => {
        render(<AppearanceCard />);
        const group = screen.getByRole('radiogroup', { name: 'Appearance' });
        expect(group).toBeTruthy();
        expect(screen.getAllByRole('radio').map((r) => r.getAttribute('aria-checked'))).toEqual(['true', 'false']);
        expect(radio(/^Daybreak$/).getAttribute('aria-checked')).toBe('true');
        expect(radio(/^Pigment$/).getAttribute('aria-checked')).toBe('false');
        // the mark is words, not colour: "In use" sits beside the saved theme only
        expect(screen.getAllByText('In use')).toHaveLength(1);
        expect(radio(/^Daybreak$/).closest('label')?.textContent).toContain('In use');
        // each choice has its one-line description, tied to the control
        expect(radio(/^Daybreak$/).getAttribute('aria-describedby')).toBeTruthy();
        expect(document.getElementById(radio(/^Daybreak$/).getAttribute('aria-describedby') as string)?.textContent).toBe('Calm blue and white. The default.');
        expect(document.getElementById(radio(/^Pigment$/).getAttribute('aria-describedby') as string)?.textContent).toBe('Warmer paper, with a colour for each form.');
        // the previews are pictures: hidden from assistive technology
        expect(document.querySelectorAll('svg[data-preview][aria-hidden="true"]')).toHaveLength(2);
    });

    it('shows a workspace that has no theme as Daybreak, and anything unknown too', () => {
        delete workspace.appTheme;
        const { unmount } = render(<AppearanceCard />);
        expect(radio(/^Daybreak$/).getAttribute('aria-checked')).toBe('true');
        unmount();
        workspace.appTheme = 'sepia';
        render(<AppearanceCard />);
        expect(radio(/^Daybreak$/).getAttribute('aria-checked')).toBe('true');
    });

    it('renders nothing, and makes no request, while the server has Pigment switched off', () => {
        permissions.appThemeEnabled = false;
        const { container } = render(<AppearanceCard />);
        expect(container.firstChild).toBeNull();
        expect(screen.queryByRole('radiogroup')).toBeNull();
        // the part that holds the mutation is never mounted
        expect(useMutation).not.toHaveBeenCalled();
        expect(save).not.toHaveBeenCalled();
    });

    it('renders nothing for a member who may not manage the workspace, switch on or not', () => {
        permissions.can = (permission) => permission !== WorkspacePermission.WORKSPACE_MANAGE;
        const { container } = render(<AppearanceCard />);
        expect(container.firstChild).toBeNull();
        expect(useMutation).not.toHaveBeenCalled();
    });

    it('keeps Save quiet until something is chosen, and says so when it is pressed anyway', () => {
        render(<AppearanceCard />);
        expect(saveButton().getAttribute('aria-disabled')).toBe('true');
        fireEvent.click(saveButton());
        expect(save).not.toHaveBeenCalled();
        expect(screen.getByRole('status').textContent).toBe('Daybreak is already in use.');
    });

    it('saves the chosen theme, announces the result and leaves focus where it was', async () => {
        render(<AppearanceCard />);
        fireEvent.click(radio(/^Pigment$/));
        expect(radio(/^Pigment$/).getAttribute('aria-checked')).toBe('true');
        expect(saveButton().getAttribute('aria-disabled')).toBeNull();
        saveButton().focus();
        fireEvent.click(saveButton());
        await waitFor(() => expect(save).toHaveBeenCalledWith({ workspaceId: 'ws-1', appTheme: 'pigment' }));
        await waitFor(() => expect(screen.getByRole('status').textContent).toBe('Saved. This workspace now uses Pigment.'));
        // the server's answer reaches the store, which the card reads: the workspace follows
        act(() => {
            workspace.appTheme = 'pigment';
        });
        expect(document.activeElement).toBe(saveButton());
        expect(screen.queryByRole('alert')).toBeNull();
    });

    it('moves the choice with the arrow keys like any radio group', async () => {
        render(<AppearanceCard />);
        const first = radio(/^Daybreak$/);
        first.focus();
        fireEvent.keyDown(first, { key: 'ArrowDown' });
        // the roving focus moves on the next tick
        await waitFor(() => expect(document.activeElement).toBe(radio(/^Pigment$/)));
        await waitFor(() => expect(radio(/^Pigment$/).getAttribute('aria-checked')).toBe('true'));
        fireEvent.keyDown(radio(/^Pigment$/), { key: 'ArrowUp' });
        await waitFor(() => expect(radio(/^Daybreak$/).getAttribute('aria-checked')).toBe('true'));
        expect(document.activeElement).toBe(radio(/^Daybreak$/));
    });

    it.each([
        [{ status: 403, data: { detail: 'Forbidden' } }, "You can't change the appearance. Ask an owner or admin of this workspace."],
        [{ status: 422, data: { code: 'app_theme_disabled', message: 'x' } }, 'Pigment is not available on this server yet. Ask whoever runs it to turn it on.'],
        [{ status: 422, data: { code: 'other' } }, 'Could not save the appearance. Check your connection and try again.'],
        [{ status: 503, data: { code: 'audit_unavailable' } }, 'Could not save the appearance. Check your connection and try again.'],
        [{ status: 'FETCH_ERROR', error: 'down' }, 'Could not save the appearance. Check your connection and try again.']
    ])('says in words why a save failed (%j)', async (error, words) => {
        save.mockResolvedValue({ error });
        render(<AppearanceCard />);
        fireEvent.click(radio(/^Pigment$/));
        saveButton().focus();
        fireEvent.click(saveButton());
        const alert = await screen.findByRole('alert');
        expect(alert.textContent).toBe(words);
        // the theme in use is unchanged, nothing says "saved", and the control keeps focus
        expect(radio(/^Daybreak$/).closest('label')?.textContent).toContain('In use');
        expect(screen.getByRole('status').textContent).toBe('');
        expect(document.activeElement).toBe(saveButton());
        // the next choice clears the message
        fireEvent.click(radio(/^Daybreak$/));
        expect(screen.queryByRole('alert')).toBeNull();
    });

    it('never shows a code or a status number', () => {
        for (const error of [{ status: 403 }, { status: 422, data: { code: 'app_theme_disabled' } }, { status: 500 }]) {
            expect(appThemeErrorKey(error)).toMatch(/^STAFF\.APP_THEME\./);
        }
        expect(appThemeErrorKey(undefined)).toBe('STAFF.APP_THEME.FAILED');
    });

    it('has no accessibility violations', async () => {
        const { container } = render(<AppearanceCard />);
        expect(await axeViolations(container)).toEqual([]);
        fireEvent.click(radio(/^Pigment$/));
        expect(await axeViolations(container)).toEqual([]);
    });

    it('is worded in Dutch too, with the same placeholders', () => {
        // eslint-disable-next-line @typescript-eslint/no-var-requires
        const en = require('../../../public/locales/en/common.json').STAFF.APP_THEME;
        // eslint-disable-next-line @typescript-eslint/no-var-requires
        const nl = require('../../../public/locales/nl/common.json').STAFF.APP_THEME;
        expect(Object.keys(nl).sort()).toEqual(Object.keys(en).sort());
        for (const key of Object.keys(en)) {
            expect([...(nl[key].match(/\{\{\w+\}\}/g) ?? [])].sort()).toEqual([...(en[key].match(/\{\{\w+\}\}/g) ?? [])].sort());
            expect(nl[key].length).toBeGreaterThan(0);
        }
        // the two names are proper nouns
        expect([nl.DAYBREAK_NAME, nl.PIGMENT_NAME]).toEqual(['Daybreak', 'Pigment']);
    });
});
