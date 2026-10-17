// When the server refuses some answers (422 invalid_answers), the respondent
// page puts its problems on the questions, in the respondent's language, and
// goes back to the first page that has one.
import React from 'react';

import { act, fireEvent, render, screen } from '@testing-library/react';
import { Provider } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import '@app/shared/hocs/i18n-provider';
import { setForm } from '@app/store/forms/slice';
import { useResponderState } from '@app/store/jotai/responder-form-state';
import { store } from '@app/store/store';

import FormSlide from './form-slide';

const submit = vi.fn();
vi.mock('@app/store/redux/form-api', async (original) => ({
    ...((await original()) as object),
    useSubmitResponseMutation: () => [submit, { isLoading: false }]
}));
vi.mock('next/navigation', () => ({
    usePathname: () => '/acme/forms/f1',
    useRouter: () => ({ push: vi.fn() })
}));
vi.mock('@app/views/organism/form-builder/fields/render-field', () => ({
    RenderImage: () => null,
    default: () => null
}));

const field = (id: string, index: number): StandardFormFieldDto => ({ id, index, type: FieldTypes.SHORT_TEXT, title: `Question ${id}` });
const slide = (id: string, index: number, fields: StandardFormFieldDto[]): StandardFormFieldDto => ({ id, index, type: FieldTypes.SLIDE, properties: { fields } });

let responder: ReturnType<typeof useResponderState> | null = null;
function Page() {
    responder = useResponderState();
    const current = Math.max(responder.responderState.currentSlide, 0);
    return <FormSlide key={current} index={current} isPreviewMode={false} />;
}

const type = async (id: string, value: string) => {
    act(() => void fireEvent.change(document.getElementById(`input-field-${id}`)!, { target: { value } }));
    await act(() => new Promise((resolve) => setTimeout(resolve, 350)));
};

describe('answers the server refused', () => {
    beforeEach(() => {
        window.PUBLIC_CONFIG = { HTTP_SCHEME: 'http://', FORM_DOMAIN: 'localhost:3000' } as any;
        Element.prototype.scrollIntoView = vi.fn();
        submit.mockReset();
    });
    afterEach(() => window.history.replaceState(null, '', '/'));

    it('are shown on their question, on the page they are on', async () => {
        window.history.replaceState(null, '', '/acme/forms/f1?lang=nl');
        submit.mockResolvedValue({ error: { status: 422, data: { code: 'invalid_answers', message: 'x', errors: [{ fieldId: 'a', rule: 'type' }] } } });
        store.dispatch(setForm({ formId: `server-${Math.random()}`, title: 'Server', fields: [slide('s1', 0, [field('a', 0)]), slide('s2', 1, [field('b', 0)])] }));
        render(
            <ReduxProvider store={store}>
                <Provider>
                    <Page />
                </Provider>
            </ReduxProvider>
        );

        act(() => responder!.setResponderState({ ...responder!.responderState, currentSlide: 0, history: [] }));
        await type('a', 'first');
        act(() => void fireEvent.click(screen.getByRole('button', { name: 'Volgende' })));
        expect(responder!.responderState.currentSlide).toBe(1);

        await type('b', 'second');
        // let the page change settle (it updates the state again after 500 ms)
        await act(() => new Promise((resolve) => setTimeout(resolve, 600)));
        await act(async () => void fireEvent.click(screen.getByRole('button', { name: 'Antwoorden versturen' })));
        expect(submit).toHaveBeenCalledTimes(1);

        await vi.waitFor(() => expect(responder!.responderState.currentSlide).toBe(0));
        expect(responder!.responderState.history).toEqual([]);
        expect(await screen.findByText('Dit antwoord kon niet worden verwerkt. Beantwoord de vraag opnieuw.')).toBeInTheDocument();
    });
});
