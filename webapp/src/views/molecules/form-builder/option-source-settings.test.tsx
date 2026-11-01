import React from 'react';

import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import i18n from 'i18next';
import { Provider, createStore } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import '@app/shared/hocs/i18n-provider';
import { setForm } from '@app/store/forms/slice';
import { activeFieldAtom, activeSlideAtom } from '@app/store/jotai/active-builder-component';
import { builderFieldsAtom, resetFromServerAtom } from '@app/store/jotai/form-document';
import { store } from '@app/store/store';
import { setWorkspace } from '@app/store/workspaces/slice';
import { axeViolations } from '@app/test/axe';

import OptionSourceSettings from './option-source-settings';

// What the server says: whether it takes sources, the lists, the forms and what a preview shows.
const served = vi.hoisted(() => ({
    enabled: true,
    previews: [] as any[],
    preview: { items: [{ id: 'li1', label: 'Amsterdam' }], total: 12, options: 12, responses: 0, truncated: false, available: true } as any
}));
vi.mock('@app/lib/hooks/use-workspace-permissions', () => ({ useWorkspacePermissions: () => ({ optionSourcesEnabled: served.enabled }) }));
vi.mock('@app/store/option-lists/api', () => ({
    useGetOptionListsQuery: () => ({
        data: [
            { id: 'l1', name: 'Municipalities', itemCount: 12 },
            { id: 'l2', name: 'Branches', itemCount: 3 }
        ]
    }),
    usePreviewOptionSourceMutation: () => [
        (args: any) => {
            served.previews.push(args);
            return Promise.resolve({ data: served.preview });
        }
    ]
}));
vi.mock('@app/store/workspaces/api', async (importOriginal) => ({
    ...(await importOriginal<typeof import('@app/store/workspaces/api')>()),
    useGetWorkspaceFormsQuery: () => ({
        data: {
            items: [
                { formId: 'form-1', title: 'This form' },
                { formId: 'people', title: 'Participants' }
            ]
        }
    }),
    useGetWorkspaceFormQuery: () => ({
        data: {
            formId: 'people',
            title: 'Participants',
            fields: [
                {
                    id: 's',
                    type: 'slide',
                    properties: {
                        fields: [
                            { id: 'name', type: 'short_text', title: 'Name', properties: { shareAsChoices: true } },
                            { id: 'nick', type: 'short_text', title: 'Nickname' },
                            { id: 'mail', type: 'email', title: 'Email', properties: { shareAsChoices: true } },
                            { id: 'role', type: 'dropdown', title: 'Role', properties: { shareAsChoices: true } }
                        ]
                    }
                }
            ]
        }
    })
}));

const question = (id: string, index: number, type: FieldTypes, title: string, properties: StandardFormFieldDto['properties'] = {}): StandardFormFieldDto => ({ id, index, type, title, properties: { fields: [], ...properties } });
const COUNTRY = question('country', 0, FieldTypes.DROP_DOWN, 'Country', { choices: [{ id: 'nl', value: 'Netherlands' }] });
const CITY = question('city', 1, FieldTypes.DROP_DOWN, 'City', { choices: [{ id: 'a', value: 'A' }], optionFilter: { fieldId: 'country', mapping: [{ when: 'nl', show: ['a'] }] } });

function setup(fields: StandardFormFieldDto[], activeId: string, slide = 'page-1') {
    const jotai = createStore();
    jotai.set(resetFromServerAtom, { formId: 'form-1', title: 'Form', fields: [{ id: slide, index: 0, type: FieldTypes.SLIDE, properties: { fields } }] } as any);
    jotai.set(activeSlideAtom, { id: slide, index: 0 });
    jotai.set(activeFieldAtom, { id: activeId, index: fields.findIndex((field) => field.id === activeId) });
    store.dispatch(setWorkspace({ id: 'ws-1', workspaceName: 'ws' }));
    store.dispatch(setForm({ formId: 'form-1', title: 'Form' } as any));
    const view = render(
        <ReduxProvider store={store}>
            <Provider store={jotai}>
                <OptionSourceSettings />
            </Provider>
        </ReduxProvider>
    );
    const fieldNow = (id: string) => jotai.get(builderFieldsAtom)[0].properties!.fields!.find((field) => field.id === id)!;
    return { jotai, view, fieldNow };
}

describe('the options source in the builder', () => {
    beforeEach(() => {
        served.enabled = true;
        served.previews = [];
        i18n.changeLanguage('en');
    });
    afterEach(cleanup);

    it('shows nothing for a question that cannot take a source, or while the server does not take them', () => {
        setup([question('name', 0, FieldTypes.SHORT_TEXT, 'Name')], 'name');
        expect(screen.queryByTestId('option-source-settings')).not.toBeInTheDocument();
        cleanup();
        served.enabled = false;
        setup([CITY], 'city');
        expect(screen.queryByTestId('option-source-settings')).not.toBeInTheDocument();
    });

    it('lists a stored source read-only while the server does not take sources', () => {
        served.enabled = false;
        setup([question('city', 0, FieldTypes.DROP_DOWN, 'City', { optionSource: { kind: 'list', listId: 'l1' } })], 'city');
        expect(screen.getByTestId('option-source-settings')).toBeDisabled();
        expect(screen.getByText(/does not take options from a list/)).toBeInTheDocument();
    });

    it('takes a list: the question loses its own options and filter, and the source is stored', async () => {
        const { fieldNow } = setup([COUNTRY, CITY], 'city');
        await act(async () => fireEvent.click(screen.getByRole('radio', { name: 'A list of this workspace' })));
        // nothing is stored until a list is picked
        expect(fieldNow('city').properties!.optionSource).toBeUndefined();
        await act(async () => fireEvent.change(screen.getByLabelText('List'), { target: { value: 'l1' } }));
        const properties = fieldNow('city').properties!;
        expect(properties.optionSource).toEqual({ kind: 'list', listId: 'l1' });
        expect(properties.choices).toEqual([]);
        expect(properties.optionFilter).toBeUndefined();
        // what it offers: counts, not the items, until asked
        await waitFor(() => expect(screen.getByTestId('option-source-preview')).toHaveTextContent('12 options'));
        expect(screen.queryByText('Amsterdam')).not.toBeInTheDocument();
        await act(async () => fireEvent.click(screen.getByRole('button', { name: 'Show the first items' })));
        expect(await screen.findByText('Amsterdam')).toBeInTheDocument();
    });

    it('makes a list depend on an earlier choice question', async () => {
        const city = question('city', 1, FieldTypes.DROP_DOWN, 'City', { optionSource: { kind: 'list', listId: 'l1' } });
        const { fieldNow } = setup([COUNTRY, city], 'city');
        await act(async () => fireEvent.change(screen.getByLabelText('Depends on the answer to'), { target: { value: 'country' } }));
        expect(fieldNow('city').properties!.optionSource).toEqual({ kind: 'list', listId: 'l1', parentFieldId: 'country' });
        await act(async () => fireEvent.change(screen.getByLabelText('Depends on the answer to'), { target: { value: '' } }));
        expect(fieldNow('city').properties!.optionSource).toEqual({ kind: 'list', listId: 'l1' });
    });

    it("another form's answers need a confirmation, name only usable questions, and warn plainly", async () => {
        const { fieldNow } = setup([COUNTRY, question('who', 1, FieldTypes.MULTIPLE_CHOICE, 'Who', { allowMultipleSelection: true })], 'who');
        await act(async () => fireEvent.click(screen.getByRole('radio', { name: 'Answers given to another form' })));
        expect(screen.getByText('People who open this form will see these answers')).toBeInTheDocument();
        // the form being edited is not offered; a question that identifies is not either
        const forms = screen.getByLabelText('Form') as HTMLSelectElement;
        expect(Array.from(forms.options).map((option) => option.textContent)).toEqual(['Pick a form', 'Participants']);
        await act(async () => fireEvent.change(forms, { target: { value: 'people' } }));
        const questions = screen.getByLabelText('Question') as HTMLSelectElement;
        // only the questions that opted in to being shown as choices (and can)
        expect(Array.from(questions.options).map((option) => option.textContent)).toEqual(['Pick a question', 'Name', 'Role']);
        await act(async () => fireEvent.change(questions, { target: { value: 'name' } }));
        const use = screen.getByRole('button', { name: 'Use these answers' });
        expect(use).toBeDisabled();
        await act(async () => fireEvent.click(screen.getByRole('checkbox', { name: /I understand that people who open this form will see these answers/ })));
        expect(use).toBeEnabled();
        await act(async () => fireEvent.click(use));
        expect(fieldNow('who').properties!.optionSource).toEqual({ kind: 'form_answers', formId: 'people', questionId: 'name' });
    });

    it('keeps the typed options aside and brings them back with own options', async () => {
        const { fieldNow } = setup([COUNTRY, CITY], 'city');
        await act(async () => fireEvent.click(screen.getByRole('radio', { name: 'A list of this workspace' })));
        await act(async () => fireEvent.change(screen.getByLabelText('List'), { target: { value: 'l1' } }));
        expect(fieldNow('city').properties!.choices).toEqual([]);
        await act(async () => fireEvent.click(screen.getByRole('radio', { name: 'Options I type here' })));
        expect(fieldNow('city').properties!.optionSource).toBeUndefined();
        expect(fieldNow('city').properties!.choices).toEqual([{ id: 'a', value: 'A' }]);
    });

    it('takes the sharing of its own answers away when a source is picked', async () => {
        const shared = question('who', 1, FieldTypes.DROP_DOWN, 'Who', { shareAsChoices: true });
        const { fieldNow } = setup([COUNTRY, shared], 'who');
        await act(async () => fireEvent.click(screen.getByRole('radio', { name: 'A list of this workspace' })));
        await act(async () => fireEvent.change(screen.getByLabelText('List'), { target: { value: 'l1' } }));
        expect(fieldNow('who').properties!.shareAsChoices).toBeUndefined();
    });

    it('can search the forms by name', async () => {
        setup([COUNTRY, question('who', 1, FieldTypes.DROP_DOWN, 'Who')], 'who');
        await act(async () => fireEvent.click(screen.getByRole('radio', { name: 'Answers given to another form' })));
        expect(screen.getByLabelText('Search forms')).toBeInTheDocument();
        expect(screen.queryByText(/Showing the first/)).not.toBeInTheDocument();
    });

    it('goes back to own options by taking the source away', async () => {
        const { fieldNow } = setup([question('city', 0, FieldTypes.DROP_DOWN, 'City', { optionSource: { kind: 'list', listId: 'l1' } })], 'city');
        await act(async () => fireEvent.click(screen.getByRole('radio', { name: 'Options I type here' })));
        expect(fieldNow('city').properties!.optionSource).toBeUndefined();
    });

    it('says when the source is empty, cut, or gone', async () => {
        served.preview = { items: [], total: 0, options: 0, responses: 0, truncated: false, available: true };
        setup([question('city', 0, FieldTypes.DROP_DOWN, 'City', { optionSource: { kind: 'list', listId: 'l1' } })], 'city');
        expect(await screen.findByText(/nothing to choose from yet/)).toBeInTheDocument();
        cleanup();
        served.preview = { items: [], total: 0, options: 1000, responses: 5, truncated: true, available: true };
        setup([question('who', 0, FieldTypes.DROP_DOWN, 'Who', { optionSource: { kind: 'form_answers', formId: 'people', questionId: 'name' } })], 'who');
        expect(await screen.findByText('Only the first 1000 options are offered.')).toBeInTheDocument();
        expect(screen.getByTestId('option-source-preview')).toHaveTextContent('from 5 responses');
        cleanup();
        served.preview = { items: [], total: 0, options: 0, responses: 0, truncated: false, available: false };
        setup([question('city', 0, FieldTypes.DROP_DOWN, 'City', { optionSource: { kind: 'list', listId: 'gone' } })], 'city');
        expect(await screen.findByText(/no longer exists/)).toBeInTheDocument();
        served.preview = { items: [{ id: 'li1', label: 'Amsterdam' }], total: 12, options: 12, responses: 0, truncated: false, available: true };
    });

    it('has no accessibility violations', async () => {
        const { view } = setup([COUNTRY, question('city', 1, FieldTypes.DROP_DOWN, 'City', { optionSource: { kind: 'list', listId: 'l1' } })], 'city');
        expect(await axeViolations(view.container)).toEqual([]);
    });
});
