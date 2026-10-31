// "Save and continue later" and the review page, together: the control is on the
// review page too, the draft remembers the last page (the place to come back to,
// from which the respondent goes on to the review again), and sending the form
// from the review deletes the draft like the last page's button does.
import React from 'react';

import { act, fireEvent, render, screen } from '@testing-library/react';
import { Provider } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ThemeColors } from '@app/constants/theme';
import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import '@app/shared/hocs/i18n-provider';
import { setAuth } from '@app/store/auth/slice';
import { setForm } from '@app/store/forms/slice';
import { useFormState } from '@app/store/jotai/form';
import { useResponderState } from '@app/store/jotai/responder-form-state';
import { store } from '@app/store/store';
import { setWorkspace } from '@app/store/workspaces/slice';
import { REVIEW_SLIDE } from '@app/utils/review-page';

import Form from './form';
import RespondentPageShell from './respondent-page-shell';

const submit = vi.fn();
const save = vi.fn();
const requestLink = vi.fn();
vi.mock('@app/store/redux/form-api', async (original) => ({
    ...((await original()) as object),
    useSubmitResponseMutation: () => [submit, { isLoading: false }],
    useSendFlowEventMutation: () => [() => ({ catch: () => {} })]
}));
vi.mock('@app/store/redux/drafts-api', async (original) => ({
    ...((await original()) as object),
    useSaveDraftMutation: () => [save, { isLoading: false }],
    useRequestDraftLinkMutation: () => [requestLink, { isLoading: false }],
    useDiscardDraftMutation: () => [vi.fn(), { isLoading: false }]
}));
vi.mock('next/navigation', () => ({ usePathname: () => '/acme/forms/f1', useRouter: () => ({ push: vi.fn() }) }));
vi.mock('@app/views/organism/form-builder/fields/render-field', () => ({ RenderImage: () => null, default: () => null }));
vi.mock('framer-motion', async (importOriginal) => ({
    ...(await importOriginal<typeof import('framer-motion')>()),
    AnimatePresence: ({ children }: { children: React.ReactNode }) => <>{children}</>
}));

const q = (id: string, title: string): StandardFormFieldDto => ({ id, index: 0, type: FieldTypes.SHORT_TEXT, title, properties: { fields: [] }, validations: { required: false } });
const page = (id: string, index: number, fields: StandardFormFieldDto[]): StandardFormFieldDto => ({ id, index, type: FieldTypes.SLIDE, title: '', properties: { fields } });
const EDIT = `${'e'.repeat(24)}.${'K'.repeat(43)}`;

let responder: ReturnType<typeof useResponderState>;
function Respondent() {
    responder = useResponderState();
    const { updateFormTheme } = useFormState();
    React.useEffect(() => {
        updateFormTheme(ThemeColors[0], { undoable: false });
    }, []);
    return (
        <RespondentPageShell>
            <Form isPreviewMode={false} />
        </RespondentPageShell>
    );
}

const click = async (name: string | RegExp) => act(async () => void fireEvent.click(await screen.findByRole('button', { name })));

const toReview = async () => {
    store.dispatch(setWorkspace({ id: 'ws-1', workspaceName: 'acme' } as any));
    store.dispatch(
        setForm({
            formId: `rd-${Math.random()}`,
            builderVersion: 'v2',
            version: 2,
            title: 'Membership',
            settings: { showReviewPage: true, allowSaveDraft: true },
            thankyouPage: [{ id: 'end', title: 'Thank you', isDefault: true }],
            fields: [page('s1', 0, [q('a', 'Your name')]), page('s2', 1, [q('b', 'Your town')])]
        } as any)
    );
    render(
        <ReduxProvider store={store}>
            <Provider>
                <Respondent />
            </Provider>
        </ReduxProvider>
    );
    act(() => responder.setResponderState({ ...responder.responderState, currentSlide: 0, prevActiveSlide: 0, history: [-1] }));
    await click('Continue');
    await screen.findByText('Page 2 of 2');
    await click('Review your answers');
    await screen.findByRole('heading', { level: 1, name: 'Review your answers' });
    expect(responder.currentSlide).toBe(REVIEW_SLIDE);
};

describe('drafts and the review page', () => {
    beforeEach(() => {
        window.PUBLIC_CONFIG = { HTTP_SCHEME: 'http://', FORM_DOMAIN: 'localhost:3000' } as any;
        Element.prototype.scrollIntoView = vi.fn();
        window.history.replaceState(null, '', '/acme/forms/f1?lang=en');
        for (const mock of [submit, save, requestLink]) mock.mockReset();
        submit.mockResolvedValue({ data: 'response-1' });
        save.mockResolvedValue({ data: { savedAt: '2026-11-01T10:00:00Z', expiresAt: '2026-12-01T10:00:00Z' } });
        requestLink.mockResolvedValue({ data: { savedAt: '2026-11-01T10:00:00Z', expiresAt: '2026-12-01T10:00:00Z', editKey: EDIT } });
    });
    afterEach(() => {
        window.history.replaceState(null, '', '/');
        store.dispatch(setAuth({ id: '', email: '' }));
    });

    it('saves from the review page, remembering the last page as the place to come back to', async () => {
        store.dispatch(setAuth({ id: 'user-1', email: 'ada@example.com' }));
        await toReview();
        await click('Save and continue later');
        expect(save).toHaveBeenCalledTimes(1);
        expect(save.mock.calls[0][0].body.position).toEqual({ pageId: 's2', history: ['s1'] });
    });

    it('sends the draft key with the submission from the review, so the server deletes the draft', async () => {
        await toReview();
        await click('Save and continue later');
        fireEvent.change(screen.getByLabelText('Your email address'), { target: { value: 'ada@example.com' } });
        await click('Send me the link');
        expect(requestLink.mock.calls[0][0].body.position).toEqual({ pageId: 's2', history: ['s1'] });
        await screen.findByText(/We sent a link/);
        await click('Submit response');
        expect(submit).toHaveBeenCalledTimes(1);
        expect((submit.mock.calls[0][0].body as FormData).get('draft_key')).toBe(EDIT);
    });
});
