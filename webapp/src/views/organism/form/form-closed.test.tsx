// A form that closes while someone is filling it in: the server refuses the
// submission (409 form_closed) and a refetch of the form brings it back
// without its questions. Neither may crash the page or lose their answers.
import React from 'react';

import { act, fireEvent, render, screen } from '@testing-library/react';
import { Provider } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ThemeColors } from '@app/constants/theme';
import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import '@app/shared/hocs/i18n-provider';
import { setForm } from '@app/store/forms/slice';
import { useFormState } from '@app/store/jotai/form';
import { useFormResponse } from '@app/store/jotai/responder-form-response';
import { useResponderState } from '@app/store/jotai/responder-form-state';
import { store } from '@app/store/store';

import Form from './form';
import FormSlide from './form-slide';

const submit = vi.fn();
vi.mock('@app/store/redux/form-api', async (original) => ({
    ...((await original()) as object),
    useSubmitResponseMutation: () => [submit, { isLoading: false }]
}));
vi.mock('next/navigation', () => ({ usePathname: () => '/acme/forms/f1', useRouter: () => ({ push: vi.fn() }) }));
vi.mock('@app/views/organism/form-builder/fields/render-field', () => ({ RenderImage: () => null, default: () => null }));
vi.mock('framer-motion', async (importOriginal) => ({
    ...(await importOriginal<typeof import('framer-motion')>()),
    AnimatePresence: ({ children }: { children: React.ReactNode }) => <>{children}</>
}));

const text = (id: string, title: string): StandardFormFieldDto => ({ id, index: 0, type: FieldTypes.SHORT_TEXT, title, properties: { fields: [] }, validations: { required: false } });
const page = (id: string, index: number, fields: StandardFormFieldDto[]): StandardFormFieldDto => ({ id, index, type: FieldTypes.SLIDE, title: '', properties: { fields } });

let responder: ReturnType<typeof useResponderState> | null = null;
let response: ReturnType<typeof useFormResponse> | null = null;

const type = async (id: string, value: string) => {
    act(() => void fireEvent.change(document.getElementById(`input-field-${id}`)!, { target: { value } }));
    await act(() => new Promise((resolve) => setTimeout(resolve, 350)));
};

const CLOSED_SUBMIT = {
    en: ['Submit response', 'This form closed before your response was sent. Your answers were not sent.'],
    nl: ['Antwoorden versturen', 'Dit formulier is gesloten voordat je antwoorden zijn verstuurd. Je antwoorden zijn niet verstuurd.']
} as const;

describe('a form that closes while it is filled in', () => {
    beforeEach(() => {
        window.PUBLIC_CONFIG = { HTTP_SCHEME: 'http://', FORM_DOMAIN: 'localhost:3000' } as any;
        Element.prototype.scrollIntoView = vi.fn();
        submit.mockReset();
    });
    afterEach(() => window.history.replaceState(null, '', '/'));

    it.each(['en', 'nl'] as const)('says so when the server refuses the submission, and keeps the answers (%s)', async (lang) => {
        window.history.replaceState(null, '', `/acme/forms/f1?lang=${lang}`);
        submit.mockResolvedValue({ error: { status: 409, data: { code: 'form_closed', message: 'x', closesAt: '2026-10-30T12:00:00+00:00' } } });
        store.dispatch(setForm({ formId: `closing-${Math.random()}`, title: 'Survey', fields: [page('s1', 0, [text('a', 'Your name')])] }));
        function Page() {
            responder = useResponderState();
            response = useFormResponse();
            return <FormSlide index={0} isPreviewMode={false} />;
        }
        render(
            <ReduxProvider store={store}>
                <Provider>
                    <Page />
                </Provider>
            </ReduxProvider>
        );
        act(() => responder!.setResponderState({ ...responder!.responderState, currentSlide: 0, history: [] }));
        await type('a', 'Ada');
        const [send, message] = CLOSED_SUBMIT[lang];
        await act(async () => void fireEvent.click(screen.getByRole('button', { name: send })));
        expect(submit).toHaveBeenCalledTimes(1);

        expect((await screen.findByRole('alert')).textContent).toBe(message);
        expect(screen.queryByText(/could not be sent|niet verstuurd\. Probeer/)).toBeNull();
        // still on the page, with the answer
        expect(responder!.responderState.currentSlide).toBe(0);
        expect((document.getElementById('input-field-a') as HTMLInputElement).value).toBe('Ada');
        expect(JSON.stringify(response!.formResponse.answers)).toContain('Ada');
    });

    it('shows the closed notice on any page when a refetch brings the form back closed, and keeps the answers', async () => {
        window.history.replaceState(null, '', '/acme/forms/f1?lang=en');
        const formId = `refetch-${Math.random()}`;
        const full = { formId, builderVersion: 'v2', title: 'Survey', fields: [page('s1', 0, [text('a', 'Your name')]), page('s2', 1, [text('b', 'Your town')])] };
        store.dispatch(setForm(full));
        function Respondent() {
            responder = useResponderState();
            response = useFormResponse();
            const { updateFormTheme } = useFormState();
            React.useEffect(() => {
                updateFormTheme(ThemeColors[0], { undoable: false });
                responder!.setResponderState({ ...responder!.responderState, currentSlide: 1, prevActiveSlide: 0, history: [0] });
            }, []);
            return <Form isPreviewMode={false} />;
        }
        render(
            <ReduxProvider store={store}>
                <Provider>
                    <Respondent />
                </Provider>
            </ReduxProvider>
        );
        await screen.findByRole('textbox', { name: 'Your town' }, { timeout: 5000 });
        await type('b', 'Utrecht');

        // the refetch (focus, reconnect) answers with the closed stub
        act(() => void store.dispatch(setForm({ formId, builderVersion: 'v2', title: 'Survey', welcomePage: {}, settings: {}, unavailable: 'closed' } as any)));
        expect((await screen.findByRole('status')).textContent).toBe('This form is closed and no longer accepts responses.');
        expect(screen.queryByRole('textbox')).toBeNull();
        expect(screen.queryByRole('button', { name: 'Start' })).toBeNull();
        // their place and answers are kept
        expect(responder!.responderState.currentSlide).toBe(1);
        expect(JSON.stringify(response!.formResponse.answers)).toContain('Utrecht');

        // reopened: the page they were on comes back with their answer
        act(() => void store.dispatch(setForm(full)));
        await screen.findByRole('textbox', { name: 'Your town' }, { timeout: 5000 });
        expect((document.getElementById('input-field-b') as HTMLInputElement).value).toBe('Utrecht');
    });
});
