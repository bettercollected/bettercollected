// Members, "What can they open?": a member's teams and the access given to them on single forms, read-only; the menu
// item shows only to owners and admins while the switch is on.
import React from 'react';

import { fireEvent, render, screen, within } from '@testing-library/react';
import i18n from 'i18next';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';

import '@app/shared/hocs/i18n-provider';
import { store } from '@app/store/store';
import { setWorkspace } from '@app/store/workspaces/slice';
import { axeViolations } from '@app/test/axe';

import MemberOptions from '../datatable/member-options';
import MemberAccessDialog from './member-access-dialog';

import commonNl from '../../../public/locales/nl/common.json';

const served = vi.hoisted(() => ({
    enabled: true,
    admin: true,
    calls: [] as any[],
    result: { data: undefined as any, isLoading: false, isError: false }
}));

vi.mock('@app/lib/hooks/use-workspace-permissions', () => ({
    useWorkspacePermissions: () => ({ formAccessEnabled: served.enabled, can: (permission: string) => served.admin && permission === 'members.manage' })
}));
vi.mock('@app/store/workspaces/form-access-api', async (original) => ({
    ...((await original()) as object),
    useGetMemberAccessQuery: (args: unknown) => {
        served.calls.push(args);
        return served.result;
    }
}));
vi.mock('@app/components/modal-views/context', () => ({ useModal: () => ({ openModal: vi.fn() }) }));

const member = { id: 'u-a', firstName: 'Anna', lastName: 'Bakker', email: 'anna@voorbeeld.example', roles: ['VIEWER'], role: 'VIEWER', joined: '2026-01-01T00:00:00' } as any;

describe('What can they open?', () => {
    beforeAll(() => {
        i18n.addResourceBundle('nl', 'common', commonNl, true, true);
    });

    afterEach(async () => {
        await i18n.changeLanguage('en');
    });

    beforeEach(() => {
        served.enabled = true;
        served.admin = true;
        served.calls = [];
        served.result = {
            data: {
                teams: [{ id: 't-1', name: 'Vrijwilligersteam', memberCount: 3 }],
                grants: [
                    { id: 'g1', subjectType: 'user', subjectId: 'u-a', role: 'REVIEWER', export: true },
                    { id: 'g2', subjectType: 'user', subjectId: 'u-a', role: 'VIEWER', export: false, formTitle: 'Join the volunteers' }
                ]
            },
            isLoading: false,
            isError: false
        };
        store.dispatch(setWorkspace({ id: 'ws-1', workspaceName: 'voorbeeld' } as any));
    });

    const open = (props: Partial<React.ComponentProps<typeof MemberAccessDialog>> = {}) =>
        render(<MemberAccessDialog workspaceId="ws-1" member={member} onClose={vi.fn()} {...props} />);

    it('reads the member\'s access from the server by workspace and member', () => {
        open();
        expect(served.calls[0]).toEqual({ workspaceId: 'ws-1', memberId: 'u-a' });
    });

    it('lists the teams and the access given on single forms, read-only', () => {
        open();
        const dialog = screen.getByRole('dialog', { name: 'What can Anna Bakker open?' });
        expect(within(dialog).getByText('Vrijwilligersteam')).toBeInTheDocument();
        expect(within(dialog).getByText('Reviewer, may export responses')).toBeInTheDocument();
        expect(within(dialog).getByText('Join the volunteers')).toBeInTheDocument();
        expect(within(dialog).getByText('A form')).toBeInTheDocument();
        expect(within(dialog).getByText(/Change this in a form's settings, under Access./)).toBeInTheDocument();
        expect(within(dialog).queryByRole('button', { name: /Remove|Delete/ })).toBeNull();
    });

    it('says that owners and admins open every form, and says when there is nothing extra', () => {
        served.result = { data: { teams: [], grants: [] }, isLoading: false, isError: false };
        open({ member: { ...member, role: 'ADMIN', roles: ['ADMIN'] } });
        expect(screen.getByText('Owners and admins open every form in the workspace.')).toBeInTheDocument();
        expect(screen.getByText('Not in any team.')).toBeInTheDocument();
        expect(screen.getByText('No access has been given to them on single forms.')).toBeInTheDocument();
    });

    it('says when it cannot load', () => {
        served.result = { data: undefined, isLoading: false, isError: true };
        open();
        expect(screen.getByRole('alert').textContent).toMatch(/could not be loaded/);
    });

    it('is Dutch in Dutch, formal', async () => {
        await i18n.changeLanguage('nl');
        open();
        expect(screen.getByRole('dialog', { name: 'Wat kan Anna Bakker openen?' })).toBeInTheDocument();
        expect(screen.getByText('Beoordelaar, mag reacties exporteren')).toBeInTheDocument();
    });

    it('has no accessibility violations', async () => {
        open();
        expect(await axeViolations(screen.getByRole('dialog'))).toEqual([]);
    });

    describe('the menu item', () => {
        const renderMenu = () =>
            render(
                <ReduxProvider store={store}>
                    <MemberOptions member={member} workspaceId="ws-1" />
                </ReduxProvider>
            );

        it('is in the member\'s menu for an owner or admin while the switch is on, and opens the view', async () => {
            renderMenu();
            fireEvent.pointerDown(screen.getByRole('button', { name: /anna@voorbeeld.example/ }), { button: 0, ctrlKey: false });
            fireEvent.click(await screen.findByRole('menuitem', { name: 'What can they open?' }));
            expect(await screen.findByRole('dialog', { name: 'What can Anna Bakker open?' })).toBeInTheDocument();
        });

        it('is not there while the switch is off, and nothing is asked for', async () => {
            served.enabled = false;
            renderMenu();
            fireEvent.pointerDown(screen.getByRole('button', { name: /anna@voorbeeld.example/ }), { button: 0, ctrlKey: false });
            await screen.findAllByRole('menuitem');
            expect(screen.queryByRole('menuitem', { name: 'What can they open?' })).toBeNull();
            expect(served.calls).toEqual([]);
        });
    });
});
