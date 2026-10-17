// Several endings: a page jump that names an ending submits the form and
// shows that ending; otherwise respondents see the default ending.
import React from 'react';

import { act, fireEvent, render, screen } from '@testing-library/react';
import { Provider } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { JUMP_TARGET_SUBMIT, LogicalOperator } from '@app/models/types/form-builder-shared';
import '@app/shared/hocs/i18n-provider';
import { setForm } from '@app/store/forms/slice';
import { useResponderState } from '@app/store/jotai/responder-form-state';
import { store } from '@app/store/store';

import FormSlide from './form-slide';
import ThankyouPage from './thankyou-page';

const submit = vi.fn();
vi.mock('@app/store/redux/form-api', async (original) => ({
    ...((await original()) as object),
    useSubmitResponseMutation: () => [submit, { isLoading: false }],
    useSendFlowEventMutation: () => [() => ({ catch: () => {} })]
}));
vi.mock('next/navigation', () => ({
    usePathname: () => '/acme/forms/f1',
    useRouter: () => ({ push: vi.fn() })
}));
vi.mock('@app/views/organism/form-builder/fields/render-field', () => ({
    RenderImage: () => null,
    default: () => null
}));

const field = (id: string): StandardFormFieldDto => ({ id, index: 0, type: FieldTypes.SHORT_TEXT, title: `Question ${id}` });
const ENDINGS = [
    { id: 'thanks', name: 'Thanks', title: 'Thank you for applying' },
    { id: 'sorry', name: 'Not eligible', title: 'Sorry, you are not eligible' }
];
const form = (endingId?: string) => ({
    formId: `endings-${Math.random()}`,
    title: 'Endings',
    thankyouPage: ENDINGS,
    fields: [
        {
            id: 's1',
            index: 0,
            type: FieldTypes.SLIDE,
            properties: {
                fields: [field('a')],
                jumps: [{ operator: LogicalOperator.AND, conditions: [{ fieldId: 'a', fieldType: FieldTypes.SHORT_TEXT, comparison: 'IS_EQUAL', value: 'no' }], target: JUMP_TARGET_SUBMIT, ...(endingId ? { endingId } : {}) }]
            }
        },
        { id: 's2', index: 1, type: FieldTypes.SLIDE, properties: { fields: [field('b')] } }
    ]
});

let responder: ReturnType<typeof useResponderState> | null = null;
function Page({ preview }: { preview: boolean }) {
    responder = useResponderState();
    if (responder.responderState.currentSlide === -2) return <ThankyouPage isPreviewMode={preview} />;
    const current = Math.max(responder.responderState.currentSlide, 0);
    return <FormSlide key={current} index={current} isPreviewMode={preview} />;
}

const start = (data: any, preview = false) => {
    store.dispatch(setForm(data));
    render(
        <ReduxProvider store={store}>
            <Provider>
                <Page preview={preview} />
            </Provider>
        </ReduxProvider>
    );
    act(() => responder!.setResponderState({ ...responder!.responderState, currentSlide: 0, history: [] }));
};

const answer = async (id: string, value: string) => {
    act(() => void fireEvent.change(document.getElementById(`input-field-${id}`)!, { target: { value } }));
    await act(() => new Promise((resolve) => setTimeout(resolve, 350)));
};

describe('ending chosen by a page jump', () => {
    beforeEach(() => {
        window.PUBLIC_CONFIG = { HTTP_SCHEME: 'http://', FORM_DOMAIN: 'localhost:3000' } as any;
        Element.prototype.scrollIntoView = vi.fn();
        submit.mockReset();
        submit.mockResolvedValue({ data: 'response-1' });
    });

    it('submits, then shows the ending the jump names', async () => {
        start(form('sorry'));
        await answer('a', 'no');
        await act(async () => void fireEvent.click(screen.getByRole('button', { name: 'Submit response' })));
        // never an ending without submitting
        expect(submit).toHaveBeenCalledTimes(1);
        await vi.waitFor(() => expect(responder!.responderState.currentSlide).toBe(-2));
        expect(responder!.responderState.endingId).toBe('sorry');
        expect(screen.getByRole('heading', { level: 1, name: 'Sorry, you are not eligible' })).toBeInTheDocument();
    });

    it('a plain submit jump shows the default ending', async () => {
        start({ ...form(), thankyouPage: [ENDINGS[0], { ...ENDINGS[1], isDefault: true }] });
        await answer('a', 'no');
        await act(async () => void fireEvent.click(screen.getByRole('button', { name: 'Submit response' })));
        await vi.waitFor(() => expect(responder!.responderState.currentSlide).toBe(-2));
        expect(responder!.responderState.endingId).toBeUndefined();
        expect(screen.getByRole('heading', { level: 1, name: 'Sorry, you are not eligible' })).toBeInTheDocument();
    });

    it('a jump to an ending that is gone shows the default ending', async () => {
        start(form('gone'));
        await answer('a', 'no');
        await act(async () => void fireEvent.click(screen.getByRole('button', { name: 'Submit response' })));
        await vi.waitFor(() => expect(responder!.responderState.currentSlide).toBe(-2));
        expect(screen.getByRole('heading', { level: 1, name: 'Thank you for applying' })).toBeInTheDocument();
    });

    it('a failed submission shows no ending, and says so by the button until the next attempt', async () => {
        submit.mockResolvedValue({ error: { status: 500 } });
        start(form('sorry'));
        await answer('a', 'no');
        await act(async () => void fireEvent.click(screen.getByRole('button', { name: 'Submit response' })));
        expect(submit).toHaveBeenCalledTimes(1);
        await act(() => new Promise((resolve) => setTimeout(resolve, 50)));
        expect(responder!.responderState.currentSlide).toBe(0);
        expect(screen.getByRole('alert')).toHaveTextContent('Your response could not be sent. Please try again.');
        // the next attempt clears it at once (this one is still on its way)
        submit.mockReturnValue(new Promise(() => {}));
        await act(async () => void fireEvent.click(screen.getByRole('button', { name: 'Submit response' })));
        expect(screen.queryByText('Your response could not be sent. Please try again.')).not.toBeInTheDocument();
    });

    it('a page whose jump will submit says Submit and is the last page', async () => {
        start(form('sorry'));
        // no jump applies yet: more pages follow
        expect(screen.getByRole('button', { name: 'Continue' })).toBeInTheDocument();
        expect(screen.getByText('Page 1 of 2')).toBeInTheDocument();
        await answer('a', 'no');
        expect(screen.getByRole('button', { name: 'Submit response' })).toBeInTheDocument();
        expect(screen.getByText('Last page')).toBeInTheDocument();
        expect(screen.queryByText('Page 1 of 2')).not.toBeInTheDocument();
        await answer('a', 'yes');
        expect(screen.getByRole('button', { name: 'Continue' })).toBeInTheDocument();
    });

    it('in preview the chosen ending is shown without submitting', async () => {
        start(form('sorry'), true);
        await answer('a', 'no');
        await act(async () => void fireEvent.click(screen.getByRole('button', { name: 'Submit response' })));
        expect(submit).not.toHaveBeenCalled();
        expect(responder!.responderState.endingId).toBe('sorry');
        expect(screen.getByRole('heading', { level: 1, name: 'Sorry, you are not eligible' })).toBeInTheDocument();
    });
});
