import React from 'react';

import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { Provider, useAtom } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { beforeEach, describe, expect, it, vi } from 'vitest';

// Mock only the mutation hook — the redux store still needs the real
// formsApi (reducer + middleware are registered at store creation).
const chatEditMock = vi.fn();
const reviewMock = vi.fn();
const applyFixMock = vi.fn();
vi.mock('@app/store/redux/form-api', async (importOriginal) => {
    const actual: any = await importOriginal();
    return {
        ...actual,
        useChatEditFormWithAIMutation: () => [chatEditMock, { isLoading: false }],
        useReviewFormWithAIMutation: () => [reviewMock, { isLoading: false }],
        useApplyAIReviewFixMutation: () => [applyFixMock]
    };
});

// Same partial-mock pattern for the memory hooks (workspacesApi reducer stays real).
const memoryQueryMock: { data: any[]; refetch: ReturnType<typeof vi.fn> } = { data: [], refetch: vi.fn() };
const deleteMemoryMock = vi.fn();
const addMemoryMock = vi.fn();
vi.mock('@app/store/workspaces/api', async (importOriginal) => {
    const actual: any = await importOriginal();
    return {
        ...actual,
        useGetAIMemoryQuery: () => memoryQueryMock,
        useDeleteAIMemoryEntryMutation: () => [deleteMemoryMock],
        useAddAIMemoryEntryMutation: () => [addMemoryMock, { isLoading: false }]
    };
});

import { initialFieldsAtom } from '@app/store/jotai/field-selectors';
import { store } from '@app/store/store';
import AIChatTab from './ai-chat-tab';

const AI_RESPONSE_FORM = {
    title: 'Test form',
    description: null,
    fields: [
        {
            id: 'page-1',
            index: 0,
            type: 'slide',
            properties: {
                fields: [
                    { id: 'f1', index: 0, type: 'short_text', title: 'Your name', properties: { fields: [] } },
                    { id: 'f2', index: 1, type: 'email', title: 'Work email', properties: { fields: [] }, validations: { required: true } }
                ]
            }
        }
    ]
};

const success = (overrides: Record<string, any> = {}) => ({
    data: {
        sessionId: 'session-1',
        reply: 'Added an email question.',
        results: [{ index: 0, op: 'add_field', ok: true, message: "Added 'Work email' (email) to page 1" }],
        form: AI_RESPONSE_FORM,
        ...overrides
    }
});

// jotai v1 has no createStore — read the canvas atom through a probe
// component mounted in the same (test-scoped) Provider.
const probe: { fields: any[] } = { fields: [] };
function FieldsProbe() {
    const [fields] = useAtom(initialFieldsAtom);
    probe.fields = fields;
    return null;
}

const renderPanel = (props: Record<string, any> = {}) =>
    render(
        <ReduxProvider store={store}>
            <Provider>
                <AIChatTab memoryPollDelaysMs={[0]} {...props} />
                <FieldsProbe />
            </Provider>
        </ReduxProvider>
    );

const sendMessage = async (text: string) => {
    fireEvent.change(screen.getByPlaceholderText('Describe a change to this form…'), { target: { value: text } });
    fireEvent.click(screen.getByLabelText('Send'));
};

describe('AIChatTab', () => {
    beforeEach(() => {
        chatEditMock.mockReset();
        reviewMock.mockReset();
        applyFixMock.mockReset();
        deleteMemoryMock.mockReset().mockResolvedValue({ data: [] });
        addMemoryMock.mockReset().mockResolvedValue({ data: [] });
        memoryQueryMock.data = [];
        memoryQueryMock.refetch = vi.fn().mockResolvedValue({ data: [] });
        // The panel persists conversations per formId — isolate tests.
        sessionStorage.clear();
    });

    it('renders the empty state with example prompts', () => {
        renderPanel();
        expect(screen.getByText(/Add a required work email question/)).toBeDefined();
    });

    it('applies a successful turn to the canvas state and shows the change list', async () => {
        chatEditMock.mockResolvedValue(success());
        renderPanel();

        await sendMessage('add a work email question');

        await waitFor(() => expect(screen.getByText('Added an email question.')).toBeDefined());
        // The per-turn change list renders the backend's OpResults verbatim.
        expect(screen.getByText("Added 'Work email' (email) to page 1")).toBeDefined();

        // The canvas state received the new fields…
        const fields = probe.fields;
        expect(fields).toHaveLength(1);
        expect(fields[0].properties!.fields![1].title).toBe('Work email');
    });

    it('REGRESSION: canvas state must not share references with the response (Redux freezes its copy)', async () => {
        chatEditMock.mockResolvedValue(success());
        renderPanel();

        await sendMessage('add a work email question');
        await waitFor(() => expect(screen.getByText('Added an email question.')).toBeDefined());

        const fields = probe.fields;
        // Not the same object graph as the response…
        expect(fields).not.toBe(AI_RESPONSE_FORM.fields);
        expect(fields[0]).not.toBe(AI_RESPONSE_FORM.fields[0]);
        expect(fields[0].properties).not.toBe(AI_RESPONSE_FORM.fields[0].properties);
        // …and not frozen by Redux — the builder's setters mutate in place.
        // (This exact sharing froze the canvas and crashed every subsequent
        // edit with "Cannot assign to read only property 'properties'".)
        expect(Object.isFrozen(fields[0])).toBe(false);
        expect(Object.isFrozen(fields[0].properties)).toBe(false);
        const mutate = () => {
            (fields[0] as any).properties = { ...fields[0].properties };
        };
        expect(mutate).not.toThrow();
    });

    it('does not touch canvas state when no op applied', async () => {
        chatEditMock.mockResolvedValue(
            success({ reply: 'Nothing to change.', results: [{ index: 0, op: 'remove_field', ok: false, message: "Field 'x' was not found" }] })
        );
        renderPanel();
        const before = probe.fields;

        await sendMessage('remove something');
        await waitFor(() => expect(screen.getByText('Nothing to change.')).toBeDefined());
        expect(screen.getByText("Field 'x' was not found")).toBeDefined();
        expect(probe.fields).toBe(before); // untouched
    });

    it('shows an honest error bubble on a failed request and changes nothing', async () => {
        chatEditMock.mockResolvedValue({ error: { status: 502, data: 'The AI returned an unusable reply — nothing was changed. Please try again.' } });
        renderPanel();
        const before = probe.fields;

        await sendMessage('do something');
        await waitFor(() => expect(screen.getByText(/unusable reply/)).toBeDefined());
        expect(probe.fields).toBe(before);
    });

    it('consumes a pending Start-with-AI prompt exactly once and auto-sends it', async () => {
        chatEditMock.mockResolvedValue(success());
        // Hydrate the form slice (the guard requires a real formId, exactly
        // as the edit page provides before the tab mounts).
        const { setForm } = await import('@app/store/forms/slice');
        store.dispatch(setForm({ formId: 'form-handoff-1', title: 'Draft' }));
        sessionStorage.setItem('bc:ai-prompt:form-handoff-1', 'Build me an RSVP form');

        renderPanel();

        await waitFor(() => expect(chatEditMock).toHaveBeenCalledTimes(1));
        expect(chatEditMock.mock.calls[0][0].body.message).toBe('Build me an RSVP form');
        // Consumed: the stash is gone, so a remount cannot double-send.
        expect(sessionStorage.getItem('bc:ai-prompt:form-handoff-1')).toBeNull();
    });

    it('memory panel shows every remembered entry with its source, and forgets in place', async () => {
        memoryQueryMock.data = [
            { id: 'm1', text: 'Always use 7-step rating scales', source: 'extracted' },
            { id: 'm2', text: 'Keep pages under 5 questions', source: 'manual' }
        ];
        renderPanel();

        fireEvent.click(screen.getByRole('button', { name: /Memory \(2\)/ }));
        expect(screen.getByText('Always use 7-step rating scales')).toBeDefined();
        expect(screen.getByText('Learned from a session')).toBeDefined();
        expect(screen.getByText('Added by you')).toBeDefined();

        fireEvent.click(screen.getByLabelText('Forget "Always use 7-step rating scales"'));
        expect(deleteMemoryMock).toHaveBeenCalledWith(expect.objectContaining({ entry_id: 'm1' }));
    });

    it('surfaces what a turn taught the assistant as a Remembered notice, with Forget undo', async () => {
        chatEditMock.mockResolvedValue(success());
        // After the turn, extraction has produced a new entry server-side.
        memoryQueryMock.refetch = vi.fn().mockResolvedValue({
            data: [{ id: 'm-new', text: 'Prefers required email questions', source: 'extracted' }]
        });
        renderPanel();

        await sendMessage('add a required work email question');
        await waitFor(() => expect(screen.getByText(/Remembered:/)).toBeDefined());
        expect(screen.getByText(/Prefers required email questions/)).toBeDefined();

        fireEvent.click(screen.getByRole('button', { name: 'Forget' }));
        await waitFor(() => expect(screen.getByText(/won't keep that/)).toBeDefined());
        expect(deleteMemoryMock).toHaveBeenCalledWith(expect.objectContaining({ entry_id: 'm-new' }));
    });

    it('does not re-announce entries that existed before the turn, or manual adds', async () => {
        chatEditMock.mockResolvedValue(success());
        memoryQueryMock.data = [{ id: 'm-old', text: 'Old preference', source: 'extracted' }];
        memoryQueryMock.refetch = vi.fn().mockResolvedValue({
            data: [
                { id: 'm-old', text: 'Old preference', source: 'extracted' },
                { id: 'm-manual', text: 'Added by hand mid-turn', source: 'manual' }
            ]
        });
        renderPanel();

        await sendMessage('change something');
        await waitFor(() => expect(screen.getByText('Added an email question.')).toBeDefined());
        await waitFor(() => expect(memoryQueryMock.refetch).toHaveBeenCalled());
        expect(screen.queryByText(/Remembered:/)).toBeNull();
    });

    it('review renders findings by severity, and applying a fix updates the canvas', async () => {
        reviewMock.mockResolvedValue({
            data: {
                summary: 'One high-severity issue found.',
                findings: [
                    {
                        severity: 'high',
                        message: 'Exact age is collected — use age ranges.',
                        fieldId: 'f-age',
                        fix: { description: 'Replace with an age-range dropdown', ops: [{ op: 'remove_field', fieldId: 'f-age' }] }
                    },
                    { severity: 'info', message: 'Consider stating a retention period.', fix: null }
                ]
            }
        });
        applyFixMock.mockResolvedValue({
            data: {
                results: [{ index: 0, op: 'remove_field', ok: true, message: 'Removed' }],
                form: AI_RESPONSE_FORM
            }
        });
        renderPanel();

        fireEvent.click(screen.getByRole('button', { name: /Review/ }));
        await waitFor(() => expect(screen.getByText('One high-severity issue found.')).toBeDefined());
        expect(screen.getByText(/Exact age is collected/)).toBeDefined();
        expect(screen.getByText(/retention period/)).toBeDefined();
        // Advice-only findings must not offer a Fix button.
        expect(screen.getAllByRole('button', { name: /^Fix:/ })).toHaveLength(1);

        fireEvent.click(screen.getByRole('button', { name: /Replace with an age-range dropdown/ }));
        await waitFor(() => expect(screen.getByText(/Fixed — Replace with an age-range dropdown/)).toBeDefined());
        expect(applyFixMock).toHaveBeenCalledWith(expect.objectContaining({ body: { ops: [{ op: 'remove_field', fieldId: 'f-age' }] } }));
        // The fix landed on the canvas through the same deepCopy path as chat.
        expect(probe.fields[0].properties!.fields![1].title).toBe('Work email');
        expect(Object.isFrozen(probe.fields[0])).toBe(false);
    });

    it('a failed fix reports the ops-engine message and changes nothing', async () => {
        reviewMock.mockResolvedValue({
            data: {
                summary: 'One issue.',
                findings: [{ severity: 'medium', message: 'Stale finding.', fix: { description: 'Remove the field', ops: [{ op: 'remove_field', fieldId: 'gone' }] } }]
            }
        });
        applyFixMock.mockResolvedValue({
            data: { results: [{ index: 0, op: 'remove_field', ok: false, message: "Field 'gone' was not found" }], form: AI_RESPONSE_FORM }
        });
        renderPanel();
        const before = probe.fields;

        fireEvent.click(screen.getByRole('button', { name: /Review/ }));
        await waitFor(() => expect(screen.getByText('One issue.')).toBeDefined());
        fireEvent.click(screen.getByRole('button', { name: /Remove the field/ }));
        await waitFor(() => expect(screen.getByText("Field 'gone' was not found")).toBeDefined());
        expect(probe.fields).toBe(before); // canvas untouched
    });

    it('shows an honest error bubble when the review itself fails', async () => {
        reviewMock.mockResolvedValue({ error: { status: 502, data: 'The AI returned an unusable review — please try again.' } });
        renderPanel();

        fireEvent.click(screen.getByRole('button', { name: /Review/ }));
        await waitFor(() => expect(screen.getByText(/unusable review/)).toBeDefined());
    });

    it('sends the sessionId on the second turn (continuity)', async () => {
        chatEditMock.mockResolvedValue(success());
        renderPanel();

        await sendMessage('first');
        await waitFor(() => expect(chatEditMock).toHaveBeenCalledTimes(1));
        expect(chatEditMock.mock.calls[0][0].body.sessionId).toBeNull();

        await sendMessage('second');
        await waitFor(() => expect(chatEditMock).toHaveBeenCalledTimes(2));
        expect(chatEditMock.mock.calls[1][0].body.sessionId).toBe('session-1');
    });

    it('REGRESSION: the conversation survives a tab switch (unmount/remount)', async () => {
        chatEditMock.mockResolvedValue(success());
        const { setForm } = await import('@app/store/forms/slice');
        store.dispatch(setForm({ formId: 'form-persist-1', title: 'Draft' }));

        const first = renderPanel();
        await sendMessage('add a work email question');
        await waitFor(() => expect(screen.getByText('Added an email question.')).toBeDefined());
        // Radix Tabs unmounts inactive tab content — this is what a switch
        // to the Design tab and back actually does to this component.
        first.unmount();

        renderPanel();
        expect(screen.getByText('add a work email question')).toBeDefined();
        expect(screen.getByText('Added an email question.')).toBeDefined();
        // …and the restored session continues, not a fresh one.
        await sendMessage('second turn');
        await waitFor(() => expect(chatEditMock).toHaveBeenCalledTimes(2));
        expect(chatEditMock.mock.calls[1][0].body.sessionId).toBe('session-1');
    });

    it('example prompts are clickable and send as a turn', async () => {
        chatEditMock.mockResolvedValue(success());
        renderPanel();

        fireEvent.click(screen.getByRole('button', { name: /Make everything on page 2 optional/ }));
        await waitFor(() => expect(chatEditMock).toHaveBeenCalledTimes(1));
        expect(chatEditMock.mock.calls[0][0].body.message).toBe('Make everything on page 2 optional');
    });

    it('a failed send offers Try again, which resends the same message', async () => {
        chatEditMock.mockResolvedValueOnce({ error: { status: 502, data: 'The AI returned an unusable reply — nothing was changed. Please try again.' } }).mockResolvedValueOnce(success());
        renderPanel();

        await sendMessage('add a phone question');
        await waitFor(() => expect(screen.getByText(/unusable reply/)).toBeDefined());

        fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
        await waitFor(() => expect(chatEditMock).toHaveBeenCalledTimes(2));
        expect(chatEditMock.mock.calls[1][0].body.message).toBe('add a phone question');
        await waitFor(() => expect(screen.getByText('Added an email question.')).toBeDefined());
    });

    it('a fix cannot be double-applied while in flight', async () => {
        reviewMock.mockResolvedValue({
            data: {
                summary: 'One issue.',
                findings: [{ severity: 'high', message: 'Needs consent.', fix: { description: 'Add consent question', ops: [{ op: 'add_page' }] } }]
            }
        });
        // Never resolves during the test — the fix stays in flight.
        applyFixMock.mockReturnValue(new Promise(() => {}));
        renderPanel();

        fireEvent.click(screen.getByRole('button', { name: /Review/ }));
        await waitFor(() => expect(screen.getByText('One issue.')).toBeDefined());

        const fixButton = screen.getByRole('button', { name: /Add consent question/ });
        fireEvent.click(fixButton);
        await waitFor(() => expect(screen.getByText('Applying…')).toBeDefined());
        fireEvent.click(screen.getByText('Applying…'));
        expect(applyFixMock).toHaveBeenCalledTimes(1);
    });
});
