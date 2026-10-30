// The respondent page when a refetch (focus, reconnect) brings the form back
// closed: the server then answers with a stub that has the welcome page and
// its look, but no questions and no endings.
import React, { Suspense } from 'react';

import { act, render, screen } from '@testing-library/react';
import { Provider } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { FieldTypes, StandardFormDto, StandardFormFieldDto } from '@app/models/dtos/form';
import { FormSlideLayout } from '@app/models/enums/form';
import '@app/shared/hocs/i18n-provider';
import { useResponderState } from '@app/store/jotai/responder-form-state';
import { store } from '@app/store/store';
import { setWorkspace } from '@app/store/workspaces/slice';

import FormPage from './page';

let query: { data?: Partial<StandardFormDto>; isLoading: boolean; error?: unknown } = { isLoading: true };
vi.mock('@app/store/workspaces/api', async (original) => ({
    ...((await original()) as object),
    useGetWorkspaceFormQuery: () => query
}));
vi.mock('@app/lib/analytics/umami', () => ({ trackCanonicalFormView: vi.fn() }));
const push = vi.hoisted(() => vi.fn());
vi.mock('next/navigation', () => ({ usePathname: () => '/acme/forms/f1', useRouter: () => ({ push }) }));
vi.mock('@app/views/organism/form-builder/fields/render-field', () => ({ RenderImage: () => null, default: () => null }));
vi.mock('framer-motion', async (importOriginal) => ({
    ...(await importOriginal<typeof import('framer-motion')>()),
    AnimatePresence: ({ children }: { children: React.ReactNode }) => <>{children}</>
}));
// The trust strip's own rendering has its tests; here: what the page tells it.
const trustProps: Array<{ layout?: FormSlideLayout; defaultExpanded?: boolean }> = [];
vi.mock('@app/views/molecules/form/trust-layer', () => ({
    default: (props: { layout?: FormSlideLayout; defaultExpanded?: boolean }) => {
        trustProps.push(props);
        return null;
    }
}));

const text = (id: string, title: string): StandardFormFieldDto => ({ id, index: 0, type: FieldTypes.SHORT_TEXT, title, properties: { fields: [] }, validations: { required: false } });
const page = (id: string, index: number, fields: StandardFormFieldDto[], layout?: FormSlideLayout): StandardFormFieldDto => ({ id, index, type: FieldTypes.SLIDE, title: '', properties: { fields, layout } });

const CLOSED = 'This form is closed and no longer accepts responses.';

const closedStub = (formId: string, extra: Partial<StandardFormDto> = {}) => ({ formId, builderVersion: 'v2', title: 'Survey', welcomePage: { layout: FormSlideLayout.TWO_COLUMN_IMAGE_LEFT }, settings: {}, unavailable: 'closed' as const, ...extra });

let responder: ReturnType<typeof useResponderState> | null = null;
function Place() {
    const state = useResponderState();
    React.useEffect(() => {
        responder = state;
    });
    return null;
}

const params = Promise.resolve({ form_id: 'f1', workspace_name: 'acme' });
const tree = () => (
    <ReduxProvider store={store}>
        <Provider>
            <Place />
            <Suspense fallback={null}>
                <FormPage params={params} />
            </Suspense>
        </Provider>
    </ReduxProvider>
);

/** Render the page (its params are a promise: wait until it is in). */
const show = async () => {
    let view: ReturnType<typeof render> | undefined;
    await act(async () => {
        view = render(tree());
    });
    return view!;
};

/** Render the page with `data` loaded, then put the respondent on `slide`. */
const open = async (data: Partial<StandardFormDto>, slide: number) => {
    query = { data, isLoading: false };
    const view = await show();
    act(() => responder!.setResponderState({ ...responder!.responderState, currentSlide: slide, prevActiveSlide: slide, history: slide >= 0 ? [-1] : [] }));
    return view;
};

/** A refetch answers with `data`. */
const refetch = async (view: ReturnType<typeof render>, data: Partial<StandardFormDto>) => {
    query = { data, isLoading: false };
    view.rerender(tree());
    await act(() => new Promise((resolve) => setTimeout(resolve, 50)));
};

describe('the respondent page when a refetch brings the form back closed', { timeout: 20000 }, () => {
    beforeEach(() => {
        window.PUBLIC_CONFIG = { HTTP_SCHEME: 'http://', FORM_DOMAIN: 'localhost:3000' } as any;
        window.history.replaceState(null, '', '/acme/forms/f1?lang=en');
        Element.prototype.scrollIntoView = vi.fn();
        // a roomy screen: the trust panel may open on the welcome page
        window.matchMedia = vi.fn().mockImplementation((q: string) => ({ matches: true, media: q, addEventListener: vi.fn(), removeEventListener: vi.fn() }));
        store.dispatch(setWorkspace({ id: 'w1', workspaceName: 'acme' } as any));
        trustProps.length = 0;
        responder = null;
    });
    afterEach(() => window.history.replaceState(null, '', '/'));

    it('keeps the custom ending a respondent is on', async () => {
        const formId = `ending-${Math.random()}`;
        const full = { formId, builderVersion: 'v2', title: 'Survey', fields: [page('s1', 0, [text('a', 'Your name')])], thankyouPage: [{ id: 'e1', title: 'Custom thanks', message: 'Your next step is X', isDefault: true }] } as any;
        const view = await open(full, -2);
        await screen.findByText('Your next step is X', undefined, { timeout: 5000 });

        await refetch(view, closedStub(formId));

        expect(screen.getByText('Custom thanks')).toBeInTheDocument();
        expect(screen.getByText('Your next step is X')).toBeInTheDocument();
        expect(screen.queryByText('Your answers have been sent.')).toBeNull();
        expect(screen.queryByText(CLOSED)).toBeNull();

        // leaving the ending: the closed form is shown
        act(() => responder!.setResponderState({ ...responder!.responderState, currentSlide: -1 }));
        expect((await screen.findByRole('status')).textContent).toBe(CLOSED);
        expect(screen.queryByText('Your next step is X')).toBeNull();
    });

    const withEnding = (formId: string) => ({ formId, builderVersion: 'v2', title: 'Survey X', fields: [page('s1', 0, [text('a', 'Your name')])], thankyouPage: [{ id: 'e1', title: 'Custom thanks', message: 'Your next step is X', isDefault: true }] }) as any;

    it("does not carry an ending over to another form that is closed: that form's closed notice", async () => {
        // a same-tab move from form X (on its ending) to form Y, which is closed
        const view = await open(withEnding(`x-${Math.random()}`), -2);
        await screen.findByText('Your next step is X', undefined, { timeout: 5000 });

        await refetch(view, closedStub(`y-${Math.random()}`, { title: 'Survey Y' }));

        expect((await screen.findByRole('status')).textContent).toBe(CLOSED);
        expect(screen.getByRole('heading', { name: 'Survey Y' })).toBeInTheDocument();
        expect(screen.queryByText('Your next step is X')).toBeNull();
        expect(responder!.responderState.currentSlide).toBe(-1);
    });

    it('starts another, open form at its welcome page, not at the ending of the previous one', async () => {
        const view = await open(withEnding(`x-${Math.random()}`), -2);
        await screen.findByText('Your next step is X', undefined, { timeout: 5000 });

        await refetch(view, { formId: `y-${Math.random()}`, builderVersion: 'v2', title: 'Survey Y', fields: [page('s1', 0, [text('b', 'Your town')])] } as any);

        expect(await screen.findByRole('button', { name: 'Start' })).toBeInTheDocument();
        expect(screen.queryByText('Your next step is X')).toBeNull();
        expect(screen.queryByText('Custom thanks')).toBeNull();
        expect(responder!.responderState.currentSlide).toBe(-1);
    });

    it('shows the closed notice to a respondent still filling it in', async () => {
        const formId = `filling-${Math.random()}`;
        const full = { formId, builderVersion: 'v2', title: 'Survey', fields: [page('s1', 0, [text('a', 'Your name')])] } as any;
        const view = await open(full, 0);
        await screen.findByRole('textbox', { name: 'Your name' }, { timeout: 5000 });

        await refetch(view, closedStub(formId));

        expect((await screen.findByRole('status')).textContent).toBe(CLOSED);
        expect(screen.queryByRole('textbox')).toBeNull();
    });

    it("lays the trust strip out for the welcome page the closed form shows, open as on the welcome page", async () => {
        const formId = `strip-${Math.random()}`;
        const full = {
            formId,
            builderVersion: 'v2',
            title: 'Survey',
            welcomePage: { layout: FormSlideLayout.TWO_COLUMN_IMAGE_LEFT },
            fields: [page('s1', 0, [text('a', 'Your name')], FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND), page('s2', 1, [text('b', 'Your town')], FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND)]
        } as any;
        const view = await open(full, 1);
        await screen.findByRole('textbox', { name: 'Your town' }, { timeout: 5000 });
        expect(trustProps.at(-1)).toMatchObject({ layout: FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND, defaultExpanded: false });

        await refetch(view, closedStub(formId));

        expect((await screen.findByRole('status')).textContent).toBe(CLOSED);
        expect(trustProps.at(-1)).toMatchObject({ layout: FormSlideLayout.TWO_COLUMN_IMAGE_LEFT, defaultExpanded: true });
    });

    it('shows the closed notice for a closed imported form set to show the original', async () => {
        // An imported (non-v2) form shown as the original: the stub has neither
        // the imported id nor the questions, so there is no original to embed.
        const formId = `imported-${Math.random()}`;
        query = { data: closedStub(formId, { builderVersion: 'v1', welcomePage: undefined, settings: { showOriginalForm: true, embedUrl: 'https://docs.example.com/form' } as any }), isLoading: false };
        await show();

        expect((await screen.findByRole('status', undefined, { timeout: 5000 })).textContent).toBe(CLOSED);
        expect(screen.getByRole('heading', { name: 'Survey' })).toBeInTheDocument();
        expect(document.querySelector('iframe')).toBeNull();
    });
});

describe('an imported form set to show the original', { timeout: 20000 }, () => {
    const upload: StandardFormFieldDto = { id: 'u1', index: 1, type: FieldTypes.FILE_UPLOAD, title: 'Attachment', properties: { fields: [] }, validations: { required: false } };
    const imported = (embedUrl: string, fields: StandardFormFieldDto[]) => ({
        formId: `imported-${Math.random()}`,
        importedFormId: 'provider-form',
        builderVersion: 'v1',
        title: 'Survey',
        settings: { showOriginalForm: true, embedUrl } as any,
        fields
    });

    beforeEach(() => {
        window.PUBLIC_CONFIG = { HTTP_SCHEME: 'http://', FORM_DOMAIN: 'localhost:3000' } as any;
        window.history.replaceState(null, '', '/acme/forms/f1?lang=en');
        Element.prototype.scrollIntoView = vi.fn();
        window.matchMedia = vi.fn().mockImplementation((q: string) => ({ matches: true, media: q, addEventListener: vi.fn(), removeEventListener: vi.fn() }));
        store.dispatch(setWorkspace({ id: 'w1', workspaceName: 'acme' } as any));
        push.mockReset();
    });
    afterEach(() => window.history.replaceState(null, '', '/'));

    it('opens an http(s) original', async () => {
        query = { data: imported('https://docs.example.com/form', [text('q1', 'Name'), upload]), isLoading: false };
        await show();

        expect(push).toHaveBeenCalledWith('https://docs.example.com/form');
    });

    it('frames an http(s) original', async () => {
        query = { data: imported('https://docs.example.com/form', [text('q1', 'Name')]), isLoading: false };
        await show();

        expect(document.querySelector('iframe')?.getAttribute('src')).toBe('https://docs.example.com/form?embedded=true');
    });

    it.each(['javascript:alert(1)', 'data:text/html,<p>x</p>', '/elsewhere'])('never opens %s', async (embedUrl) => {
        query = { data: imported(embedUrl, [text('q1', 'Name'), upload]), isLoading: false };
        await show();
        await act(() => new Promise((resolve) => setTimeout(resolve, 50)));

        expect(push).not.toHaveBeenCalled();
    });

    it.each(['javascript:alert(1)', 'data:text/html,<p>x</p>'])('never frames %s', async (embedUrl) => {
        query = { data: imported(embedUrl, [text('q1', 'Name')]), isLoading: false };
        await show();

        expect(document.querySelector('iframe')).toBeNull();
    });
});
