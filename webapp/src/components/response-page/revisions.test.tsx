import React from 'react';

import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import i18n from 'i18next';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import '@app/shared/hocs/i18n-provider';
import { store } from '@app/store/store';
import { axeViolations } from '@app/test/axe';

import EditAnswers from './edit-answers';
import ResponseHistory from './response-history';

const editMock = vi.fn();
const loadValues = vi.fn();
const history: { data: any; isLoading: boolean; isError: boolean } = { data: undefined, isLoading: false, isError: false };
const valuesState: { data: any; isFetching: boolean; isError: boolean } = { data: undefined, isFetching: false, isError: false };
vi.mock('@app/store/workspaces/response-revisions-api', async (importOriginal) => {
    const actual: any = await importOriginal();
    return {
        ...actual,
        useEditResponseAnswersMutation: () => [editMock, { isLoading: false }],
        useGetResponseRevisionsQuery: () => ({ ...history, refetch: vi.fn() }),
        useLazyGetResponseRevisionValuesQuery: () => [loadValues, valuesState]
    };
});
const toast = vi.fn();
vi.mock('@app/shadcn/components/ui/use-toast', async (importOriginal) => {
    const actual: any = await importOriginal();
    return { ...actual, useToast: () => ({ toast }) };
});

const q = (id: string, type: string, title: string, extra: Record<string, any> = {}): any => ({ id, type, title, ...extra });
const FORM: any = {
    formId: 'f1',
    fields: [
        {
            id: 'p1',
            type: 'slide',
            properties: {
                fields: [
                    q('name', 'short_text', 'Your name', { validations: { required: true } }),
                    q('age', 'number', 'Age'),
                    q('sig', 'signature', 'Signature'),
                    q('home', 'address', 'Home address'),
                    q('ref', 'short_text', 'Reference', { internal: true })
                ]
            }
        }
    ]
};
const ANSWERS: any = { name: { type: 'text', text: 'Ada' }, age: { type: 'number', number: 36 } };

const wrapper = ({ children }: { children: React.ReactNode }) => <ReduxProvider store={store}>{children}</ReduxProvider>;
const renderEdit = () => render(<EditAnswers workspaceId="ws1" formId="f1" responseId="r1" form={FORM} answers={ANSWERS} />, { wrapper });
const open = () => fireEvent.click(screen.getByRole('button', { name: 'Edit answers' }));

beforeEach(() => {
    editMock.mockReset();
    loadValues.mockReset();
    toast.mockReset();
    history.data = { revisions: [] };
    history.isLoading = false;
    history.isError = false;
    valuesState.data = undefined;
    valuesState.isFetching = false;
    valuesState.isError = false;
});
afterEach(async () => {
    await i18n.changeLanguage('en');
});

describe('editing answers', () => {
    it('opens with the stored answers, the editable questions only, and says what cannot be changed', () => {
        renderEdit();
        open();
        const dialog = screen.getByRole('dialog');
        expect(within(dialog).getByLabelText(/Your name/)).toHaveValue('Ada');
        expect(within(dialog).getByLabelText(/Age/)).toHaveValue(36);
        // an internal field has its own panel; a signature and an address cannot be changed here
        expect(within(dialog).queryByLabelText(/Reference/)).toBeNull();
        expect(within(dialog).getByTestId('locked-questions')).toHaveTextContent('These cannot be changed here: Signature, Home address.');
        expect(within(dialog).getByText(/The respondent is not told, and nothing is sent on again/)).toBeInTheDocument();
        expect(within(dialog).getByRole('button', { name: 'Save 0 changes' })).toBeDisabled();
    });

    it('sends only what changed and closes with a message', async () => {
        editMock.mockResolvedValue({ data: { changed: ['name'], revision: 1 } });
        renderEdit();
        open();
        const dialog = screen.getByRole('dialog');
        fireEvent.change(within(dialog).getByLabelText(/Your name/), { target: { value: 'Ada Lovelace' } });
        fireEvent.click(within(dialog).getByRole('button', { name: 'Save 1 change' }));
        await waitFor(() => expect(editMock).toHaveBeenCalledWith({ workspaceId: 'ws1', formId: 'f1', responseId: 'r1', answers: { name: { field: { id: 'name' }, type: 'text', text: 'Ada Lovelace' } } }));
        await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
        expect(toast).toHaveBeenCalledWith({ description: 'Saved. 1 answer was changed.' });
    });

    it('keeps the dialog open and says why when the server refuses', async () => {
        editMock.mockResolvedValue({ error: { status: 422, data: 'Age must be at most 120.' } });
        renderEdit();
        open();
        const dialog = screen.getByRole('dialog');
        fireEvent.change(within(dialog).getByLabelText(/Age/), { target: { value: '500' } });
        fireEvent.click(within(dialog).getByRole('button', { name: 'Save 1 change' }));
        expect(await within(dialog).findByText('Age must be at most 120.')).toBeInTheDocument();
        expect(screen.getByRole('dialog')).toBeInTheDocument();
        expect(toast).not.toHaveBeenCalled();
    });

    it('words the codes the server gives', async () => {
        editMock.mockResolvedValue({ error: { status: 409, data: { code: 'deletion_requested', message: 'x' } } });
        renderEdit();
        open();
        const dialog = screen.getByRole('dialog');
        fireEvent.change(within(dialog).getByLabelText(/Your name/), { target: { value: 'Eve' } });
        fireEvent.click(within(dialog).getByRole('button', { name: 'Save 1 change' }));
        expect(await within(dialog).findByText("This response has a deletion request, so it can't be edited.")).toBeInTheDocument();
    });

    it('starts again from the stored answers each time it is opened', () => {
        renderEdit();
        open();
        fireEvent.change(within(screen.getByRole('dialog')).getByLabelText(/Your name/), { target: { value: 'Changed' } });
        fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Cancel' }));
        open();
        expect(within(screen.getByRole('dialog')).getByLabelText(/Your name/)).toHaveValue('Ada');
    });

    it('speaks Dutch to the staff', async () => {
        await i18n.changeLanguage('nl');
        renderEdit();
        fireEvent.click(screen.getByRole('button', { name: 'Antwoorden bewerken' }));
        const dialog = screen.getByRole('dialog');
        expect(within(dialog).getByTestId('locked-questions')).toHaveTextContent('Deze kunnen hier niet worden gewijzigd');
        fireEvent.change(within(dialog).getByLabelText(/Your name/), { target: { value: 'Eve' } });
        expect(within(dialog).getByRole('button', { name: '1 wijziging opslaan' })).toBeEnabled();
    });

    it('has no accessibility violations while open', async () => {
        renderEdit();
        open();
        expect(await axeViolations(screen.getByRole('dialog'))).toEqual([]);
    });
});

describe('the history', () => {
    const entries = [
        { seq: 1, at: '2026-10-30T10:00:00Z', actor: { kind: 'respondent', former: false }, changed: [{ id: 'name', title: 'Your name' }] },
        {
            seq: 2,
            at: '2026-10-31T09:00:00Z',
            actor: { kind: 'staff', name: 'Sam Jansen', role: 'EDITOR', former: false },
            changed: [
                { id: 'age', title: 'Age' },
                { id: 'name', title: 'Your name' }
            ]
        }
    ];
    const renderHistory = () => render(<ResponseHistory workspaceId="ws1" formId="f1" responseId="r1" form={FORM} />, { wrapper });

    it('lists who changed what and when, newest first, without any value', () => {
        history.data = { revisions: entries };
        renderHistory();
        const items = screen.getAllByRole('listitem');
        expect(items[0]).toHaveTextContent('Sam Jansen (Editor) changed 2 answers');
        expect(items[0]).toHaveTextContent('Age, Your name');
        expect(items[1]).toHaveTextContent('The respondent changed 1 answer');
        expect(screen.queryByTestId('revision-values-1')).toBeNull();
        expect(screen.queryByText('Ada')).toBeNull();
    });

    it('says plainly that nothing was changed', () => {
        renderHistory();
        expect(screen.getByText('No answer has been changed since this response was submitted.')).toBeInTheDocument();
    });

    it('asks for the previous values only when told to, and forgets them when hidden', () => {
        history.data = { revisions: entries };
        renderHistory();
        const first = screen.getByTestId('revision-1');
        expect(loadValues).not.toHaveBeenCalled();
        valuesState.data = { seq: 1, values: { name: { type: 'text', text: 'Ada' } } };
        fireEvent.click(within(first).getByRole('button', { name: 'Show previous values' }));
        expect(loadValues).toHaveBeenCalledWith({ workspaceId: 'ws1', formId: 'f1', responseId: 'r1', seq: 1 });
        expect(within(screen.getByTestId('revision-values-1')).getByText('Ada')).toBeInTheDocument();
        fireEvent.click(within(first).getByRole('button', { name: 'Hide previous values' }));
        expect(screen.queryByTestId('revision-values-1')).toBeNull();
    });

    it('shows "No answer" for a question that had none', () => {
        history.data = { revisions: entries };
        renderHistory();
        valuesState.data = { seq: 2, values: { age: null, name: { type: 'text', text: 'Ada' } } };
        fireEvent.click(within(screen.getByTestId('revision-2')).getByRole('button', { name: 'Show previous values' }));
        expect(within(screen.getByTestId('revision-values-2')).getByText('No answer')).toBeInTheDocument();
    });

    it('names a former member by the role they held, never an id', () => {
        history.data = { revisions: [{ seq: 1, at: '2026-10-31T09:00:00Z', actor: { kind: 'staff', role: 'ADMIN', former: true }, changed: [{ id: 'age', title: 'Age' }] }] };
        renderHistory();
        expect(screen.getByText('A former team member (Admin)')).toBeInTheDocument();
    });

    it('says when it failed to load, with a way to try again', () => {
        history.data = undefined;
        history.isError = true;
        renderHistory();
        expect(screen.getByRole('alert')).toHaveTextContent('The history could not be loaded.');
        expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument();
    });

    it('speaks Dutch to the staff', async () => {
        await i18n.changeLanguage('nl');
        history.data = { revisions: entries };
        renderHistory();
        expect(screen.getByRole('heading', { name: 'Geschiedenis' })).toBeInTheDocument();
        expect(screen.getAllByRole('listitem')[0]).toHaveTextContent('Sam Jansen (Bewerker) heeft 2 antwoorden gewijzigd');
    });

    it('has no accessibility violations', async () => {
        history.data = { revisions: entries };
        const { container } = renderHistory();
        expect(await axeViolations(container)).toEqual([]);
    });
});
