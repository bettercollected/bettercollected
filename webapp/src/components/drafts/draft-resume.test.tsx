// Coming back to a saved draft: from the link in the address (read once and
// removed from the address bar) or, signed in, from the account. The answers,
// the hidden-field values and the page come back, and the page says what
// happened: restored, the form changed, the form no longer takes responses,
// the link does not work. English and Dutch, accessible.
import React from 'react';

import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { Provider } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ThemeColors } from '@app/constants/theme';
import { FieldTypes, StandardFormDto, StandardFormFieldDto } from '@app/models/dtos/form';
import '@app/shared/hocs/i18n-provider';
import { setAuth } from '@app/store/auth/slice';
import { setForm } from '@app/store/forms/slice';
import { useFormState } from '@app/store/jotai/form';
import { useRespondentDraft } from '@app/store/jotai/respondent-draft';
import { useFormResponse } from '@app/store/jotai/responder-form-response';
import { useResponderState } from '@app/store/jotai/responder-form-state';
import { useHiddenFieldValues } from '@app/store/jotai/responder-hidden-fields';
import { store } from '@app/store/store';
import { setWorkspace } from '@app/store/workspaces/slice';
import { axeViolations } from '@app/test/axe';
import { forgetResumeToken, takeResumeToken } from '@app/utils/form-drafts';
import Form from '@app/views/organism/form/form';
import RespondentPageShell from '@app/views/organism/form/respondent-page-shell';

import DraftResume from './draft-resume';

const openDraft = vi.fn();
const getMyDraft = vi.fn();
const discard = vi.fn();
vi.mock('@app/store/redux/drafts-api', async (original) => ({
    ...((await original()) as object),
    useOpenDraftMutation: () => [openDraft, { isLoading: false }],
    useGetMyDraftMutation: () => [getMyDraft, { isLoading: false }],
    useDiscardDraftMutation: () => [discard, { isLoading: false }],
    useSaveDraftMutation: () => [vi.fn(), { isLoading: false }],
    useRequestDraftLinkMutation: () => [vi.fn(), { isLoading: false }]
}));
vi.mock('next/navigation', () => ({ usePathname: () => '/acme/forms/f1', useRouter: () => ({ push: vi.fn() }) }));
vi.mock('@app/views/organism/form-builder/fields/render-field', () => ({ RenderImage: () => null, default: () => null }));
vi.mock('framer-motion', async (importOriginal) => ({
    ...(await importOriginal<typeof import('framer-motion')>()),
    AnimatePresence: ({ children }: { children: React.ReactNode }) => <>{children}</>
}));

const text = (id: string, title: string): StandardFormFieldDto => ({ id, index: 0, type: FieldTypes.SHORT_TEXT, title, properties: { fields: [] }, validations: { required: false } });
const page = (id: string, index: number, fields: StandardFormFieldDto[]): StandardFormFieldDto => ({ id, index, type: FieldTypes.SLIDE, title: '', properties: { fields } });

const TOKEN = `${'a'.repeat(24)}.${'T'.repeat(43)}`;
const EDIT = `${'b'.repeat(24)}.${'E'.repeat(43)}`;
const SAVED = { savedAt: '2026-10-20T08:00:00Z', expiresAt: '2026-11-19T08:00:00Z', formVersion: 2, currentVersion: 2, formChanged: false };
const ANSWERS = { a: { type: 'text', text: 'Ada' }, b: { type: 'text', text: 'Utrecht' } };

const FORM = {
    formId: 'form-1',
    builderVersion: 'v2',
    title: 'Survey',
    version: 2,
    hiddenFields: ['source'],
    settings: { allowSaveDraft: true },
    fields: [page('p1', 0, [text('a', 'Your name')]), page('p2', 1, [text('b', 'Your town')])]
} as unknown as StandardFormDto;

let probe: { responder: ReturnType<typeof useResponderState>; response: ReturnType<typeof useFormResponse>; hidden: ReturnType<typeof useHiddenFieldValues>; draft: ReturnType<typeof useRespondentDraft> } | null = null;

function Page({ form }: { form: StandardFormDto }) {
    // as the form page does: the link is taken from the address bar as the page starts
    const [token] = React.useState(() => takeResumeToken());
    probe = { responder: useResponderState(), response: useFormResponse(), hidden: useHiddenFieldValues(), draft: useRespondentDraft() };
    const { updateFormTheme } = useFormState();
    React.useEffect(() => {
        updateFormTheme(ThemeColors[0], { undoable: false });
    }, []);
    return (
        <RespondentPageShell notice={<DraftResume form={form} token={token} />}>
            <Form isPreviewMode={false} />
        </RespondentPageShell>
    );
}

const show = (form: StandardFormDto = FORM, shown: Partial<StandardFormDto> = form) => {
    store.dispatch(setWorkspace({ id: 'ws-1', workspaceName: 'acme' } as any));
    store.dispatch(setForm(shown as any));
    return render(
        <ReduxProvider store={store}>
            <Provider>
                <Page form={form} />
            </Provider>
        </ReduxProvider>
    );
};

const link = (lang = 'en') => window.history.replaceState(null, '', `/acme/forms/f1?lang=${lang}#resume=${TOKEN}`);

describe('resuming a saved draft', () => {
    beforeEach(() => {
        window.PUBLIC_CONFIG = { HTTP_SCHEME: 'http://', FORM_DOMAIN: 'localhost:3000' } as any;
        Element.prototype.scrollIntoView = vi.fn();
        for (const mock of [openDraft, getMyDraft, discard]) mock.mockReset();
        probe = null;
        forgetResumeToken();
    });
    afterEach(() => {
        forgetResumeToken();
        window.history.replaceState(null, '', '/');
        store.dispatch(setAuth({ id: '', email: '' }));
    });

    it.each([
        ['en', 'We restored your draft from 20 October 2026. Check your answers, then continue.'],
        ['nl', 'We hebben je concept van 20 oktober 2026 teruggezet. Controleer je antwoorden en ga daarna verder.']
    ])('opens the link, takes the token out of the address bar, and puts answers, hidden values and the page back (%s)', async (lang, notice) => {
        link(lang);
        openDraft.mockResolvedValue({ data: { ...SAVED, answers: ANSWERS, hiddenFields: { source: 'newsletter', other: 'x' }, position: { pageId: 'p2', history: ['p1'] }, editKey: EDIT } });
        show();
        await screen.findByRole('textbox', { name: lang === 'en' ? 'Your town' : 'Your town' });

        expect(openDraft).toHaveBeenCalledTimes(1);
        expect(openDraft).toHaveBeenCalledWith({ workspaceId: 'ws-1', formId: 'form-1', token: TOKEN });
        // the token is a credential: gone from the address bar at once
        expect(window.location.hash).toBe('');
        expect(window.location.search).toBe(`?lang=${lang}`);
        expect(document.body.innerHTML).not.toContain(TOKEN);

        expect((document.getElementById('input-field-b') as HTMLInputElement).value).toBe('Utrecht');
        expect(probe!.responder.responderState).toMatchObject({ currentSlide: 1, history: [-1, 0] });
        expect(probe!.response.formResponse.answers).toMatchObject(ANSWERS);
        // only names the form declares come back
        expect(probe!.hidden.hiddenValues).toEqual({ source: 'newsletter' });
        // the browser can save from here, and the submit will delete the draft
        expect(probe!.draft.draft).toMatchObject({ editKey: EDIT, status: 'resumed' });
        expect((await screen.findByTestId('draft-notice')).textContent).toBe(notice);
    });

    it('keeps what the share link carries over what was saved', async () => {
        link();
        openDraft.mockResolvedValue({ data: { ...SAVED, answers: {}, hiddenFields: { source: 'saved' }, position: null } });
        store.dispatch(setWorkspace({ id: 'ws-1', workspaceName: 'acme' } as any));
        store.dispatch(setForm(FORM as any));
        function Seeded() {
            const { setHiddenValues } = useHiddenFieldValues();
            React.useEffect(() => setHiddenValues({ source: 'from-link' }), []);
            return <Page form={FORM} />;
        }
        render(
            <ReduxProvider store={store}>
                <Provider>
                    <Seeded />
                </Provider>
            </ReduxProvider>
        );
        await screen.findByTestId('draft-notice');
        expect(probe!.hidden.hiddenValues).toEqual({ source: 'from-link' });
    });

    it('says when the form changed since, and how many answers no longer fit', async () => {
        link();
        openDraft.mockResolvedValue({ data: { ...SAVED, formChanged: true, currentVersion: 3, answers: { ...ANSWERS, gone: { type: 'text', text: 'x' } }, hiddenFields: {}, position: { pageId: 'removed', history: [] } } });
        show();
        const notice = await screen.findByTestId('draft-notice');
        expect(notice.textContent).toBe('This form changed after you saved your draft. We restored the answers that still fit. Please check them. 1 answer no longer fits a question in the form and was left out.');
        // the page they were on is gone: the first page
        expect(probe!.responder.responderState).toMatchObject({ currentSlide: 0, history: [-1] });
        expect(probe!.response.formResponse.answers.gone).toBeUndefined();
        expect(probe!.response.formResponse.answers.a).toBeTruthy();
    });

    it.each([
        ['closed', 'You have a saved draft, but this form is closed and takes no more responses. Your draft is deleted on 19 November 2026, or now if you choose.'],
        ['not_yet_open', 'You have a saved draft, but this form is not open yet. Your draft is deleted on 19 November 2026, or now if you choose.'],
        ['full', 'You have a saved draft, but this form has received all the responses it accepts. Your draft is deleted on 19 November 2026, or now if you choose.']
    ])('a form that is %s hands back no answers, says so and lets them delete the draft', async (reason, notice) => {
        link();
        openDraft.mockResolvedValue({ data: { unavailable: reason, expiresAt: SAVED.expiresAt } });
        discard.mockResolvedValue({ data: { deleted: true } });
        show(FORM, { ...FORM, fields: undefined, unavailable: reason } as any);
        expect((await screen.findByTestId('draft-notice')).textContent).toContain(notice);
        expect(Object.keys(probe!.response.formResponse.answers)).toEqual([]);

        fireEvent.click(screen.getByRole('button', { name: 'Delete the draft now' }));
        await waitFor(() => expect(screen.queryByTestId('draft-notice')).toBeNull());
        expect(discard).toHaveBeenCalledWith({ workspaceId: 'ws-1', formId: 'form-1', token: TOKEN });
    });

    it('says the link does not work (404) or could not be opened (anything else), and the form starts as usual', async () => {
        link();
        openDraft.mockResolvedValue({ error: { status: 404, data: { code: 'draft_not_found' } } });
        const first = show();
        expect((await screen.findByTestId('draft-notice')).textContent).toBe('This link no longer works. A link stops working after 7 days, when a newer link is sent, or when the draft is deleted. You can start again.');
        expect(probe!.responder.responderState.currentSlide).toBe(-1);
        first.unmount();

        link();
        openDraft.mockResolvedValue({ error: { status: 500 } });
        show();
        expect((await screen.findByTestId('draft-notice')).textContent).toBe('We could not open your draft. Check your connection and open the link again.');
    });

    it('the note can be dismissed', async () => {
        link();
        openDraft.mockResolvedValue({ data: { ...SAVED, answers: ANSWERS, hiddenFields: {}, position: null } });
        show();
        await screen.findByTestId('draft-notice');
        fireEvent.click(screen.getByRole('button', { name: 'Dismiss' }));
        expect(screen.queryByTestId('draft-notice')).toBeNull();
    });

    it('takes the link out of the address bar before the form has loaded, and opens it once it has', async () => {
        link();
        openDraft.mockResolvedValue({ data: { ...SAVED, answers: ANSWERS, hiddenFields: {}, position: null } });
        function Starting() {
            // the page starts (takes the link) but the form is still loading
            const [token] = React.useState(() => takeResumeToken());
            const [loaded, setLoaded] = React.useState(false);
            return (
                <>
                    <button onClick={() => setLoaded(true)}>loaded</button>
                    {loaded && <DraftResume form={FORM} token={token} />}
                </>
            );
        }
        store.dispatch(setWorkspace({ id: 'ws-1', workspaceName: 'acme' } as any));
        store.dispatch(setForm(FORM as any));
        render(
            <ReduxProvider store={store}>
                <Provider>
                    <Starting />
                </Provider>
            </ReduxProvider>
        );
        expect(window.location.hash).toBe('');
        expect(window.location.href).not.toContain(TOKEN);
        expect(openDraft).not.toHaveBeenCalled();
        fireEvent.click(screen.getByRole('button', { name: 'loaded' }));
        await waitFor(() => expect(openDraft).toHaveBeenCalledWith({ workspaceId: 'ws-1', formId: 'form-1', token: TOKEN }));
    });

    it('ignores an address fragment that is not a link in its exact shape', async () => {
        window.history.replaceState(null, '', `/acme/forms/f1?lang=en#resume=${TOKEN}x`);
        show();
        await screen.findByRole('button', { name: 'Start' });
        expect(openDraft).not.toHaveBeenCalled();
        expect(getMyDraft).not.toHaveBeenCalled();
    });

    it('signed in, picks up the account draft without a link; none (404) is silent', async () => {
        store.dispatch(setAuth({ id: 'user-1', email: 'ada@example.com' }));
        getMyDraft.mockResolvedValue({ error: { status: 404, data: { code: 'draft_not_found' } } });
        const none = show();
        await screen.findByRole('button', { name: 'Start' });
        await waitFor(() => expect(getMyDraft).toHaveBeenCalledWith({ workspaceId: 'ws-1', formId: 'form-1' }));
        expect(screen.queryByTestId('draft-notice')).toBeNull();
        expect(openDraft).not.toHaveBeenCalled();
        none.unmount();

        getMyDraft.mockReset();
        getMyDraft.mockResolvedValue({ data: { ...SAVED, answers: ANSWERS, hiddenFields: {}, position: { pageId: 'p2', history: ['p1'] } } });
        show();
        await screen.findByRole('textbox', { name: 'Your town' });
        expect(probe!.draft.draft).toMatchObject({ status: 'resumed', editKey: undefined });
        expect(getMyDraft).toHaveBeenCalledTimes(1);
    });

    it('does nothing for a form that keeps no drafts', async () => {
        link();
        const form = { ...FORM, settings: {} } as unknown as StandardFormDto;
        show(form);
        await screen.findByRole('button', { name: 'Start' });
        expect(openDraft).not.toHaveBeenCalled();
        expect(getMyDraft).not.toHaveBeenCalled();
        expect(screen.queryByTestId('draft-notice')).toBeNull();
    });

    it('opens the link once, however often the page renders', async () => {
        link();
        openDraft.mockResolvedValue({ data: { ...SAVED, answers: ANSWERS, hiddenFields: {}, position: null } });
        const view = show();
        await screen.findByTestId('draft-notice');
        act(() => void store.dispatch(setForm({ ...FORM } as any)));
        view.rerender(
            <ReduxProvider store={store}>
                <Provider>
                    <Page form={{ ...FORM }} />
                </Provider>
            </ReduxProvider>
        );
        expect(openDraft).toHaveBeenCalledTimes(1);
    });
});

describe.each(['en', 'nl'] as const)('the draft notes pass axe (%s)', (lang) => {
    beforeEach(() => {
        window.PUBLIC_CONFIG = { HTTP_SCHEME: 'http://', FORM_DOMAIN: 'localhost:3000' } as any;
        Element.prototype.scrollIntoView = vi.fn();
        for (const mock of [openDraft, getMyDraft, discard]) mock.mockReset();
        forgetResumeToken();
    });
    afterEach(() => {
        forgetResumeToken();
        window.history.replaceState(null, '', '/');
    });

    it.each([
        ['restored', { data: { ...SAVED, answers: ANSWERS, hiddenFields: {}, position: null } }],
        ['changed', { data: { ...SAVED, formChanged: true, answers: { ...ANSWERS, gone: { type: 'text' } }, hiddenFields: {}, position: null } }],
        ['unavailable', { data: { unavailable: 'closed', expiresAt: SAVED.expiresAt } }],
        ['a dead link', { error: { status: 404 } }]
    ])('%s', async (_name, result) => {
        link(lang);
        openDraft.mockResolvedValue(result);
        show();
        await screen.findByTestId('draft-notice');
        const violations = await axeViolations(document, { page: false });
        expect(violations).toEqual([]);
        expect(document.querySelector('[data-testid="draft-notice"]')!.closest('[role="status"]')).toHaveAttribute('aria-label', lang === 'en' ? 'About your draft' : 'Over je concept');
    });
});
