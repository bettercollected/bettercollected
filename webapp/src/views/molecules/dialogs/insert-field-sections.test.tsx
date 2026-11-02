import React from 'react';

import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { Provider } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import '@app/shared/hocs/i18n-provider';
import { store } from '@app/store/store';
import { setWorkspace } from '@app/store/workspaces/slice';

import InsertFieldComponent from './insert-field-modal';

const served = vi.hoisted(() => ({ enabled: true, inserted: [] as any[] }));
vi.mock('@app/lib/hooks/use-workspace-permissions', () => ({
    useWorkspacePermissions: () => ({ newQuestionTypesEnabled: false, addressQuestionEnabled: false, signatureQuestionEnabled: false, layoutContainersEnabled: false, reusableSectionsEnabled: served.enabled })
}));
vi.mock('@app/store/reusable-sections/api', () => ({
    useGetSectionsQuery: () => ({
        data: [
            { id: 's1', name: 'Applicant details', version: 2, questionCount: 5 },
            { id: 's2', name: 'Address', version: 1, questionCount: 1 }
        ]
    })
}));
vi.mock('@app/lib/hooks/use-reusable-sections', () => ({
    useSectionActions: () => ({
        insert: (...args: any[]) => {
            served.inserted.push(args);
            return Promise.resolve(true);
        }
    })
}));

const pages = (): StandardFormFieldDto[] => [{ id: 'page-1', index: 0, type: FieldTypes.SLIDE, properties: { fields: [{ id: 'q-1', index: 0, type: FieldTypes.SHORT_TEXT, title: 'Name' }] } } as StandardFormFieldDto];

const mount = (closeDropdown = vi.fn()) =>
    render(
        <ReduxProvider store={store}>
            <Provider>
                <InsertFieldComponent formFields={pages()} activeSlideComponent={{ id: 'page-1', index: 0 }} closeDropdown={closeDropdown} />
            </Provider>
        </ReduxProvider>
    );

beforeEach(() => {
    store.dispatch(setWorkspace({ id: 'w1', workspaceName: 'acme' } as any));
    served.enabled = true;
    served.inserted = [];
});
afterEach(cleanup);

describe('the Insert menu with a library', () => {
    it('lists the workspace sections as a group of their own', () => {
        mount();
        const group = screen.getByRole('group', { name: 'Sections' });
        const names = within(group)
            .getAllByRole('option')
            .map((option) => option.textContent);
        expect(names[0]).toContain('Applicant details');
        expect(names[0]).toContain('Reusable section, 5 questions, version 2');
        expect(names[1]).toContain('Address');
        expect(names[1]).toContain('Reusable section, 1 question, version 1');
    });

    it('finds a section by name', () => {
        mount();
        fireEvent.change(screen.getByRole('combobox'), { target: { value: 'applicant' } });
        expect(screen.getAllByRole('option').map((o) => o.textContent)).toEqual([expect.stringContaining('Applicant details')]);
    });

    it('copies the picked section into the selected page and closes', () => {
        const close = vi.fn();
        mount(close);
        fireEvent.click(screen.getByRole('option', { name: /Applicant details/ }));
        expect(close).toHaveBeenCalled();
        expect(served.inserted).toEqual([['s1', undefined, { id: 'page-1', index: 0 }]]);
    });

    it('offers no sections while the server has no library', () => {
        served.enabled = false;
        mount();
        expect(screen.queryByRole('group', { name: 'Sections' })).toBeNull();
    });
});
