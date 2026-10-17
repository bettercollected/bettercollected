import React from 'react';

import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { Provider, useAtom } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { BEFORE_FORM, PROPOSAL } from '@app/utils/ai-proposal.fixtures';

const chatEditMock = vi.fn();
const acceptMock = vi.fn();
const rejectMock = vi.fn();
vi.mock('@app/store/redux/form-api', async (importOriginal) => {
    const actual: any = await importOriginal();
    return {
        ...actual,
        useChatEditFormWithAIMutation: () => [chatEditMock, { isLoading: false }],
        useReviewFormWithAIMutation: () => [vi.fn(), { isLoading: false }],
        useApplyAIReviewFixMutation: () => [vi.fn()],
        useAcceptAIProposalMutation: () => [acceptMock],
        useRejectAIProposalMutation: () => [rejectMock]
    };
});

const AI_ON = { enabled: true, provider: 'openai', providerName: 'OpenAI', providers: [{ id: 'openai', name: 'OpenAI', configured: true }], canManage: true, learnPreferences: false };
vi.mock('@app/store/workspaces/api', async (importOriginal) => {
    const actual: any = await importOriginal();
    return {
        ...actual,
        useGetAISettingsQuery: () => ({ data: AI_ON, refetch: vi.fn() }),
        useUpdateAISettingsMutation: () => [vi.fn(), { isLoading: false }],
        useUpdateAIMemorySettingsMutation: () => [vi.fn()],
        useGetAIMemoryQuery: () => ({ data: [], refetch: vi.fn() }),
        useDeleteAIMemoryEntryMutation: () => [vi.fn()],
        useAddAIMemoryEntryMutation: () => [vi.fn(), { isLoading: false }]
    };
});

// The save queue's flush, observed: every call is logged with the accept
// calls so the order can be checked.
const calls: string[] = [];
const flushMock = vi.fn();
vi.mock('@app/views/molecules/form-builder/audo-save-form', async (importOriginal) => {
    const actual: any = await importOriginal();
    return { ...actual, flushAutosave: (...args: any[]) => flushMock(...args) };
});

// The canvas parts the preview renders; the editors are not under test.
vi.mock('@app/views/molecules/rich-text-editor', () => ({ RichTextEditor: ({ field }: any) => <div data-testid={`editor-${field.id}`} /> }));
vi.mock('@app/views/organism/form-builder/fields/render-field', () => ({ default: () => null }));
vi.mock('@app/views/molecules/form-builder/plain-language-hints', () => ({ default: () => null }));
vi.mock('@app/lib/hooks/use-form-logo', () => ({ useBuilderFormLogo: () => null }));
vi.mock('next/navigation', () => ({ usePathname: () => '/acme/dashboard/forms/form-1/edit', useRouter: () => ({ push: vi.fn(), replace: vi.fn() }), useSearchParams: () => new URLSearchParams() }));

import { useOpenAIProposal } from '@app/store/jotai/ai-proposal';
import useFormFieldsAtom, { initialFieldsAtom } from '@app/store/jotai/field-selectors';
import { formStateAtom } from '@app/store/jotai/form';
import { setForm } from '@app/store/forms/slice';
import { store } from '@app/store/store';
import { setWorkspace } from '@app/store/workspaces/slice';
import { deepCopy } from '@app/utils/object-utils';

import AIChatTab from './ai-chat-tab';
import { AIProposalPreviewCanvas } from './ai-proposal-preview';

const ACCEPTED_FORM = { ...deepCopy(PROPOSAL.form), updatedAt: '2026-10-17T10:00:00.000Z' };

const probe: { fields: any[]; formState?: any; preview?: any; open?: any } = { fields: [] };
function Probe() {
    const [fields] = useAtom(initialFieldsAtom);
    const [formState] = useAtom(formStateAtom);
    const { preview, openProposal } = useOpenAIProposal();
    probe.fields = fields;
    probe.formState = formState;
    probe.preview = preview;
    probe.open = openProposal;
    return null;
}

// The editor's canvas state before the AI turn.
function Seed() {
    const { initFormFields } = useFormFieldsAtom();
    React.useEffect(() => {
        initFormFields(deepCopy(BEFORE_FORM.fields) as any);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);
    return null;
}

const renderPanel = (extra?: React.ReactNode) =>
    render(
        <ReduxProvider store={store}>
            <Provider>
                <Seed />
                <AIChatTab memoryPollDelaysMs={[]} />
                {extra}
                <Probe />
            </Provider>
        </ReduxProvider>
    );

const proposeTurn = () => ({ data: { sessionId: 'session-1', reply: PROPOSAL.summary, results: PROPOSAL.results, form: null, proposal: deepCopy(PROPOSAL) } });

const ask = async () => {
    fireEvent.change(screen.getByPlaceholderText('Describe a change to this form…'), { target: { value: 'tidy up the form' } });
    fireEvent.click(screen.getByLabelText('Send'));
    await screen.findByTestId('ai-proposal');
};

describe('AI proposals in the AI tab', () => {
    beforeEach(() => {
        sessionStorage.clear();
        calls.length = 0;
        chatEditMock.mockReset().mockImplementation(async () => {
            calls.push('chat');
            return proposeTurn();
        });
        rejectMock.mockReset().mockResolvedValue({ data: { status: 'rejected' } });
        flushMock.mockReset().mockImplementation(async () => {
            calls.push('flush');
            return 'saved';
        });
        acceptMock.mockReset().mockImplementation(async (request: any) => {
            calls.push('accept');
            return { data: { proposalId: PROPOSAL.id, status: 'accepted', acceptedOpIndexes: request.opIndexes ?? [0, 1, 2, 3, 4], results: [], form: deepCopy(ACCEPTED_FORM) } };
        });
        store.dispatch(setWorkspace({ id: 'ws-1', workspaceName: 'acme' } as any));
        store.dispatch(setForm({ ...deepCopy(BEFORE_FORM), formId: 'form-1' } as any));
    });

    it('asks for a proposal and shows it as a list of labelled checkboxes, changing nothing', async () => {
        renderPanel();
        await ask();

        expect(chatEditMock.mock.calls[0][0].body.mode).toBe('propose');
        const card = screen.getByTestId('ai-proposal');
        // focus moves to the proposal
        await waitFor(() => expect(document.activeElement?.textContent).toBe('Proposed changes'));
        const pageTwo = within(card).getByRole('list', { name: 'Page 2' });
        expect(within(pageTwo).getAllByRole('listitem')).toHaveLength(2);
        const box = within(card).getByRole('checkbox', { name: "Added question 'Postcode' on page 2" });
        expect((box as HTMLInputElement).checked).toBe(true);
        expect(within(card).getByRole('checkbox', { name: 'Changed theme to Plain' })).toBeDefined();
        // the op that failed is listed, without a checkbox
        expect(within(card).getByText("Field 'nope' was not found.")).toBeDefined();
        // the canvas is untouched; the proposal is open for the canvas marks
        expect(probe.fields).toEqual(BEFORE_FORM.fields);
        expect(probe.open?.proposal.id).toBe(PROPOSAL.id);
    });

    it('Accept all saves pending edits first, then applies the returned form', async () => {
        renderPanel();
        await ask();
        fireEvent.click(screen.getByRole('button', { name: 'Accept all' }));

        await screen.findByText(/Applied 5 of 5 changes/);
        expect(calls).toEqual(['flush', 'chat', 'flush', 'accept']);
        expect(acceptMock.mock.calls[0][0]).toEqual({ workspaceId: 'ws-1', formId: 'form-1', proposalId: PROPOSAL.id, opIndexes: undefined });
        expect(probe.fields).toHaveLength(2);
        expect(probe.fields[1].id).toBe('page-2');
        // not the response's objects (Redux freezes those)
        expect(probe.fields).not.toBe(ACCEPTED_FORM.fields);
        expect(probe.open).toBeNull();
        expect(screen.queryByRole('button', { name: 'Accept all' })).toBeNull();
    });

    it('Accept selected sends the chosen ops, with the ops they build on', async () => {
        renderPanel();
        await ask();
        // leaving out the new page leaves out the question on it
        fireEvent.click(screen.getByRole('checkbox', { name: 'Added page 2' }));
        expect((screen.getByRole('checkbox', { name: "Added question 'Postcode' on page 2" }) as HTMLInputElement).checked).toBe(false);
        fireEvent.click(screen.getByRole('checkbox', { name: 'Changed theme to Plain' }));
        fireEvent.click(screen.getByRole('button', { name: 'Accept selected (2)' }));

        await screen.findByText(/Applied 2 of 5 changes/);
        expect(acceptMock.mock.calls[0][0].opIndexes).toEqual([3, 4]);
    });

    it('Discard changes nothing and tells the server', async () => {
        renderPanel();
        await ask();
        fireEvent.click(screen.getByRole('button', { name: 'Discard' }));

        await screen.findByText('Discarded. Nothing was changed.');
        expect(rejectMock).toHaveBeenCalledWith({ workspaceId: 'ws-1', formId: 'form-1', proposalId: PROPOSAL.id });
        expect(acceptMock).not.toHaveBeenCalled();
        // only the save before asking
        expect(flushMock).toHaveBeenCalledTimes(1);
        expect(probe.fields).toEqual(BEFORE_FORM.fields);
        expect(probe.open).toBeNull();
    });

    it('does not accept while local edits cannot be saved', async () => {
        renderPanel();
        await ask();
        flushMock.mockResolvedValue('conflict');
        fireEvent.click(screen.getByRole('button', { name: 'Accept all' }));

        expect((await screen.findByRole('alert')).textContent).toMatch(/changed somewhere else/);
        expect(acceptMock).not.toHaveBeenCalled();
        expect(probe.fields).toEqual(BEFORE_FORM.fields);
        // still open, to try again
        expect(screen.getByRole('button', { name: 'Accept all' })).toBeDefined();
    });

    it('shows why a stale proposal was refused, per change', async () => {
        acceptMock.mockResolvedValue({
            error: { status: 409, data: { code: 'proposal_stale', message: 'The form changed since this was proposed.', errors: [{ index: 4, message: "Field 'f1' was not found." }] } }
        });
        renderPanel();
        await ask();
        fireEvent.click(screen.getByRole('button', { name: 'Accept all' }));

        expect((await screen.findByRole('alert')).textContent).toBe('The form changed since this was proposed.');
        expect(screen.getByText("Field 'f1' was not found.")).toBeDefined();
        expect(screen.getByText(/Not applied: this form changed since the suggestion/)).toBeDefined();
        expect(probe.fields).toEqual(BEFORE_FORM.fields);
        expect(probe.open).toBeNull();
    });

    it('a proposal for an older version of the form offers to ask again', async () => {
        acceptMock.mockResolvedValue({ error: { status: 409, data: { code: 'proposal_stale', message: 'This form changed since the suggestion. Ask again.', errors: [] } } });
        renderPanel();
        await ask();
        fireEvent.click(screen.getByRole('button', { name: 'Accept all' }));

        await screen.findByText('Not applied: this form changed since the suggestion. Ask again.');
        // said once, not also as an alert
        expect(screen.queryByRole('alert')).toBeNull();
        expect(probe.fields).toEqual(BEFORE_FORM.fields);

        calls.length = 0;
        fireEvent.click(screen.getByRole('button', { name: 'Ask again' }));
        await waitFor(() => expect(chatEditMock).toHaveBeenCalledTimes(2));
        // the same prompt, after saving pending edits
        expect(chatEditMock.mock.calls[1][0].body.message).toBe('tidy up the form');
        expect(calls).toEqual(['flush', 'chat']);
    });

    it('saves pending edits before asking, and asks nothing when they cannot be saved', async () => {
        flushMock.mockResolvedValue('error');
        renderPanel();
        fireEvent.change(screen.getByPlaceholderText('Describe a change to this form…'), { target: { value: 'tidy up the form' } });
        fireEvent.click(screen.getByLabelText('Send'));

        await screen.findByText(/Your latest edits aren't saved yet, so nothing was sent/);
        expect(chatEditMock).not.toHaveBeenCalled();
        // one click retries the message
        flushMock.mockResolvedValue('saved');
        fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
        await screen.findByTestId('ai-proposal');
        expect(chatEditMock.mock.calls[0][0].body.message).toBe('tidy up the form');
    });

    it('a newer proposal sets the open one aside', async () => {
        renderPanel();
        await ask();
        chatEditMock.mockResolvedValue({ data: { ...proposeTurn().data, proposal: { ...deepCopy(PROPOSAL), id: 'aaaaaaaaaaaaaaaaaaaaaaaa-0000000000000001' } } });
        fireEvent.change(screen.getByPlaceholderText('Describe a change to this form…'), { target: { value: 'again' } });
        fireEvent.click(screen.getByLabelText('Send'));

        await screen.findByText('Replaced by a newer proposal. Nothing was changed.');
        expect(rejectMock).toHaveBeenCalledWith(expect.objectContaining({ proposalId: PROPOSAL.id }));
        expect(probe.open?.proposal.id).toBe('aaaaaaaaaaaaaaaaaaaaaaaa-0000000000000001');
    });

    it('Preview shows the proposed page read-only without touching the editor state', async () => {
        renderPanel(<AIProposalPreviewCanvas activeSlideId="page-1" />);
        await ask();
        const fieldsBefore = probe.fields;
        const formStateBefore = probe.formState;
        expect(screen.queryByTestId('ai-proposal-preview')).toBeNull();

        fireEvent.click(screen.getByRole('button', { name: 'Preview' }));
        const preview = await screen.findByTestId('ai-proposal-preview');
        expect(preview.hasAttribute('inert')).toBe(true);
        expect(screen.getByRole('button', { name: 'Preview' }).getAttribute('aria-pressed')).toBe('true');
        // the proposal's page 1, its changed question marked
        expect(within(preview).getByTestId('editor-f1')).toBeDefined();
        expect(within(preview).getByTestId('ai-mark-f1').textContent).toBe('AI · changed');

        // "Preview page" for page 2 shows the new question, marked as new
        fireEvent.click(screen.getAllByRole('button', { name: 'Preview page' })[1]);
        await waitFor(() => expect(within(screen.getByTestId('ai-proposal-preview')).getByTestId('ai-mark-f-post').textContent).toBe('AI · new'));

        // the editor state is the same objects as before
        expect(probe.fields).toBe(fieldsBefore);
        expect(probe.formState).toBe(formStateBefore);
        expect(probe.fields).toEqual(BEFORE_FORM.fields);

        act(() => {
            fireEvent.click(screen.getByRole('button', { name: 'Preview' }));
        });
        expect(screen.queryByTestId('ai-proposal-preview')).toBeNull();
    });
});
