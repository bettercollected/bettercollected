import React from 'react';

import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import '@app/shared/hocs/i18n-provider';
import { store } from '@app/store/store';
import { setWorkspace } from '@app/store/workspaces/slice';

import FieldLibrarySection, { ContainerLibrarySection } from './field-library-section';

const served = vi.hoisted(() => ({
    enabled: true,
    canEdit: true,
    saved: [] as any[],
    copies: [] as any[],
    plans: [] as any[],
    sections: [{ id: 's1', name: 'Applicant', version: 2, questionCount: 3 }] as any[],
    container: undefined as any
}));
vi.mock('@app/lib/hooks/use-workspace-permissions', () => ({ useWorkspacePermissions: () => ({ reusableSectionsEnabled: served.enabled, can: () => served.canEdit }) }));
vi.mock('@app/store/reusable-sections/api', () => ({ useGetSectionsQuery: () => ({ data: served.sections }) }));
vi.mock('@app/store/jotai/entity-hooks', () => ({
    usePageShell: () => ({ id: 'p1', properties: { containers: served.container ? [served.container] : [] } }),
    usePageFieldIds: () => ['q1', 'q2']
}));
vi.mock('@app/lib/hooks/use-reusable-sections', () => ({
    useSectionActions: () => ({
        saveAsSection: (args: any) => {
            served.saved.push(args);
            return Promise.resolve({ id: 's9', name: args.name, warnings: [] });
        },
        saveCopy: (...args: any[]) => {
            served.copies.push(args);
            return Promise.resolve({ id: 's1', version: 3, warnings: [] });
        },
        planUpdate: (...args: any[]) => {
            served.plans.push(args);
            return Promise.resolve({ sectionId: 's1', version: 2, baseKnown: true, instance: 'i1', changes: [], fields: [], containers: [], replaceIds: [] });
        },
        applyUpdate: () => true
    })
}));

const field = (extra: any = {}) => ({ id: 'q1', index: 0, type: 'short_text', title: 'Name', properties: {}, ...extra }) as any;
const mount = (ui: React.ReactElement) => render(<ReduxProvider store={store}>{ui}</ReduxProvider>);

beforeEach(() => {
    store.dispatch(setWorkspace({ id: 'w1', workspaceName: 'acme' } as any));
    served.enabled = true;
    served.canEdit = true;
    served.saved = [];
    served.copies = [];
    served.plans = [];
    served.container = undefined;
});
afterEach(cleanup);

describe("the inspector's Library section", () => {
    it('is not there while the server has no library, or for someone who cannot edit', () => {
        served.enabled = false;
        const { container } = mount(<FieldLibrarySection field={field()} pageId="p1" />);
        expect(container.textContent).toBe('');
        cleanup();
        served.enabled = true;
        served.canEdit = false;
        expect(mount(<FieldLibrarySection field={field()} pageId="p1" />).container.textContent).toBe('');
    });

    it('is not there for a staff-only question', () => {
        expect(mount(<FieldLibrarySection field={field({ internal: true })} pageId="p1" />).container.textContent).toBe('');
    });

    it('saves the question as a section with the name given', async () => {
        mount(<FieldLibrarySection field={field()} pageId="p1" />);
        fireEvent.click(screen.getByRole('button', { name: 'Save as reusable section…' }));
        fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'Name block' } });
        fireEvent.click(screen.getByRole('button', { name: 'Save to library' }));
        await waitFor(() => expect(served.saved).toEqual([{ pageId: 'p1', fieldIds: ['q1'], name: 'Name block', description: '' }]));
    });

    it('offers the whole container too, and saves its members with it', async () => {
        served.container = { id: 'box', type: 'panel', title: 'Box', fields: ['q1', 'q2'] };
        mount(<FieldLibrarySection field={field()} pageId="p1" />);
        fireEvent.click(screen.getByRole('button', { name: 'Save the panel as reusable section…' }));
        fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'Pair' } });
        fireEvent.click(screen.getByRole('button', { name: 'Save to library' }));
        await waitFor(() => expect(served.saved).toEqual([{ pageId: 'p1', fieldIds: ['q1', 'q2'], containerId: 'box', name: 'Pair', description: '' }]));
    });

    it('says which section a copy came from, and updates or saves it back', async () => {
        const copy = field({ properties: { library: { sectionId: 's1', version: 1, key: 'k', instance: 'i1' } } });
        mount(<FieldLibrarySection field={copy} pageId="p1" />);
        expect(screen.getByText('Copied from the library section “Applicant”, version 1.')).toBeTruthy();
        fireEvent.click(screen.getByRole('button', { name: 'Save this copy to the library as a new version' }));
        await waitFor(() => expect(served.copies).toEqual([['p1', 'i1']]));
        fireEvent.click(screen.getByRole('button', { name: 'Update from library…' }));
        await waitFor(() => expect(served.plans).toEqual([['p1', 'i1']]));
        expect(await screen.findByText('This copy is up to date with the library.')).toBeTruthy();
    });

    it('says so when the section is gone from the library', () => {
        served.sections = [];
        mount(<FieldLibrarySection field={field({ properties: { library: { sectionId: 'gone', version: 1, key: 'k', instance: 'i1' } } })} pageId="p1" />);
        expect(screen.getByText('Copied from a library section that is no longer in the library.')).toBeTruthy();
        expect(screen.queryByRole('button', { name: 'Update from library…' })).toBeNull();
        served.sections = [{ id: 's1', name: 'Applicant', version: 2, questionCount: 3 }];
    });
});

describe("a container's Library section", () => {
    it('saves the container with its questions', async () => {
        served.container = { id: 'box', type: 'fieldset', title: 'Details', fields: ['q1', 'q2'] };
        mount(<ContainerLibrarySection pageId="p1" containerId="box" />);
        fireEvent.click(screen.getByRole('button', { name: 'Save the field set as reusable section…' }));
        // the container's title is the suggested name
        expect((screen.getByLabelText('Name') as HTMLInputElement).value).toBe('Details');
        fireEvent.click(screen.getByRole('button', { name: 'Save to library' }));
        await waitFor(() => expect(served.saved).toEqual([{ pageId: 'p1', fieldIds: ['q1', 'q2'], containerId: 'box', name: 'Details', description: '' }]));
    });
});
