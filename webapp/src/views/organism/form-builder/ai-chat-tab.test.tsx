import React from 'react';

import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { Provider, useAtom } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { beforeEach, describe, expect, it, vi } from 'vitest';

// Mock only the mutation hook — the redux store still needs the real
// formsApi (reducer + middleware are registered at store creation).
const chatEditMock = vi.fn();
vi.mock('@app/store/redux/form-api', async (importOriginal) => {
    const actual: any = await importOriginal();
    return {
        ...actual,
        useChatEditFormWithAIMutation: () => [chatEditMock, { isLoading: false }]
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

const renderPanel = () =>
    render(
        <ReduxProvider store={store}>
            <Provider>
                <AIChatTab />
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
});
