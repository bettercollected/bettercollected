// The server refuses a submission it got too many of (429 rate_limited with
// Retry-After): the respondent is told so in their language by the button, and
// their answers stay.
import React from 'react';

import { act, fireEvent, render, screen } from '@testing-library/react';
import { Provider } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import '@app/shared/hocs/i18n-provider';
import { setForm } from '@app/store/forms/slice';
import { useFormResponse } from '@app/store/jotai/responder-form-response';
import { useResponderState } from '@app/store/jotai/responder-form-state';
import { store } from '@app/store/store';

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

const LIMITED = {
    en: ['Submit response', 'Too many responses were sent from here just now. Your answers are kept and were not sent. Please wait a minute and try again.'],
    nl: ['Antwoorden versturen', 'Er zijn zojuist te veel antwoorden vanaf hier verstuurd. Je antwoorden zijn bewaard en nog niet verstuurd. Wacht een minuut en probeer het opnieuw.']
} as const;

describe('a submission the server refuses as too many', () => {
    beforeEach(() => {
        window.PUBLIC_CONFIG = { HTTP_SCHEME: 'http://', FORM_DOMAIN: 'localhost:3000' } as any;
        Element.prototype.scrollIntoView = vi.fn();
        submit.mockReset();
    });

    it.each(['en', 'nl'] as const)('says so by the button and keeps the answers (%s)', async (lang) => {
        window.history.replaceState(null, '', `/acme/forms/f1?lang=${lang}`);
        submit.mockResolvedValue({ error: { status: 429, data: { code: 'rate_limited', message: 'x', retry_after: 30 } } });
        store.dispatch(setForm({ formId: `limited-${Math.random()}`, title: 'Survey', fields: [page('s1', 0, [text('a', 'Your name')])] }));
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
        const [send, message] = LIMITED[lang];
        await act(async () => void fireEvent.click(screen.getByRole('button', { name: send })));
        expect(submit).toHaveBeenCalledTimes(1);

        expect((await screen.findByRole('alert')).textContent).toBe(message);
        expect(responder!.responderState.currentSlide).toBe(0);
        expect(JSON.stringify(response!.formResponse.answers)).toContain('Ada');
    });
});
