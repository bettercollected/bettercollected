import React from 'react';

import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import '@app/shared/hocs/i18n-provider';
import { store } from '@app/store/store';
import { setWorkspace } from '@app/store/workspaces/slice';

import SectionsClient from './sections-client';

const served = vi.hoisted(() => ({ canEdit: true, renamed: [] as any[], deleted: [] as any[], rename: { data: {} } as any }));
vi.mock('@app/shadcn/components/ui/use-toast', () => ({ useToast: () => ({ toast: vi.fn() }) }));
vi.mock('@app/lib/hooks/use-workspace-permissions', () => ({ useWorkspacePermissions: () => ({ can: () => served.canEdit }) }));
const SECTIONS = vi.hoisted(() => [
    { id: 's1', name: 'Applicant', description: 'A person', version: 2, questionCount: 5, updatedAt: '2026-11-01T10:00:00Z' },
    { id: 's2', name: 'Address', description: null, version: 1, questionCount: 1 }
]);
const DETAIL = vi.hoisted(() => ({
    id: 's1',
    name: 'Applicant',
    version: 2,
    questionCount: 2,
    versions: [2, 1],
    warnings: [],
    fields: [
        { id: 'a', type: 'short_text', title: 'Full name' },
        { id: 'b', type: 'email', title: { type: 'doc', content: [{ type: 'paragraph', content: [{ type: 'text', text: 'Email' }] }] } }
    ],
    containers: [{ id: 'c1', type: 'panel', title: 'P', fields: ['a'] }]
}));
vi.mock('@app/store/reusable-sections/api', () => ({
    useGetSectionsQuery: () => ({ data: SECTIONS, isLoading: false }),
    useGetSectionQuery: () => ({ data: DETAIL, isLoading: false }),
    useUpdateSectionDetailsMutation: () => [
        (args: any) => {
            served.renamed.push(args);
            return Promise.resolve(served.rename);
        }
    ],
    useDeleteSectionMutation: () => [
        (args: any) => {
            served.deleted.push(args);
            return Promise.resolve({ data: null });
        }
    ]
}));

const mount = () =>
    render(
        <ReduxProvider store={store}>
            <SectionsClient />
        </ReduxProvider>
    );

beforeEach(() => {
    store.dispatch(setWorkspace({ id: 'w1', workspaceName: 'acme' } as any));
    served.canEdit = true;
    served.renamed = [];
    served.deleted = [];
    served.rename = { data: {} };
});
afterEach(cleanup);

describe('the library page', () => {
    it('lists the sections with their question count and version', () => {
        mount();
        expect(screen.getByText('Applicant')).toBeTruthy();
        expect(screen.getByText('A person')).toBeTruthy();
        expect(screen.getByText('5 questions')).toBeTruthy();
        expect(screen.getByText('1 question')).toBeTruthy();
        expect(screen.getByText('Version 2')).toBeTruthy();
    });

    it('searches by name', () => {
        mount();
        fireEvent.change(screen.getByLabelText('Search sections'), { target: { value: 'addr' } });
        expect(screen.queryByText('Applicant')).toBeNull();
        expect(screen.getByText('Address')).toBeTruthy();
        fireEvent.change(screen.getByLabelText('Search sections'), { target: { value: 'zzz' } });
        expect(screen.getByText(/No section matches/)).toBeTruthy();
    });

    it('shows the questions of a section, rich titles as text, read-only', () => {
        mount();
        fireEvent.click(screen.getByRole('button', { name: 'Show the questions of Applicant' }));
        expect(screen.getByText('Full name')).toBeTruthy();
        expect(screen.getByText('Email')).toBeTruthy();
        expect(screen.getByText('Grouped in 1 panel, field set or tabs.')).toBeTruthy();
    });

    it('renames a section', async () => {
        mount();
        fireEvent.click(screen.getByRole('button', { name: 'Rename Applicant' }));
        fireEvent.change(screen.getByLabelText('Name'), { target: { value: ' Person ' } });
        fireEvent.click(screen.getByRole('button', { name: 'Rename' }));
        await waitFor(() => expect(served.renamed).toEqual([{ workspaceId: 'w1', sectionId: 's1', name: 'Person' }]));
    });

    it('says when the name is taken', async () => {
        served.rename = { error: { data: { code: 'name_taken', message: 'x' } } };
        mount();
        fireEvent.click(screen.getByRole('button', { name: 'Rename Applicant' }));
        fireEvent.click(screen.getByRole('button', { name: 'Rename' }));
        expect((await screen.findByRole('alert')).textContent).toContain('already exists');
    });

    it('deletes only after the person confirms', async () => {
        const confirm = vi.spyOn(window, 'confirm');
        confirm.mockReturnValueOnce(false);
        mount();
        fireEvent.click(screen.getByRole('button', { name: 'Delete Applicant' }));
        expect(served.deleted).toEqual([]);
        confirm.mockReturnValueOnce(true);
        fireEvent.click(screen.getByRole('button', { name: 'Delete Applicant' }));
        await waitFor(() => expect(served.deleted).toEqual([{ workspaceId: 'w1', sectionId: 's1' }]));
        expect(String(confirm.mock.calls[1][0])).toContain('Forms that already contain a copy keep it');
        confirm.mockRestore();
    });

    it('offers nothing to change to someone who may only read', () => {
        served.canEdit = false;
        mount();
        expect(screen.queryByRole('button', { name: /Rename|Delete/ })).toBeNull();
        expect(screen.getByRole('button', { name: 'Show the questions of Applicant' })).toBeTruthy();
    });
});
