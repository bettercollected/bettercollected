// The automatic spam check on the respondent's submit: the calculation starts
// after the first interaction (never on load, never in preview), the proof goes
// in the X-BC-Captcha header, a refused proof is replaced once and a network
// error never retried, the wait is announced politely after 1.5 s, and the
// failure says what to do. English and Dutch.
import React from 'react';

import { act, fireEvent, render, screen } from '@testing-library/react';
import { Provider } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import '@app/shared/hocs/i18n-provider';
import { setForm } from '@app/store/forms/slice';
import { useResponderState } from '@app/store/jotai/responder-form-state';
import { setWorkspace } from '@app/store/workspaces/slice';
import { store } from '@app/store/store';
import { axeViolations } from '@app/test/axe';
import { resetCaptchaPasses } from '@app/utils/captcha/captcha-pass';
import { CaptchaUnavailable, solveChallenge } from '@app/utils/captcha/solve';

import FormSlide from './form-slide';

const submit = vi.fn();
const issue = vi.fn();
vi.mock('@app/store/redux/form-api', async (original) => ({
    ...((await original()) as object),
    useSubmitResponseMutation: () => [submit, { isLoading: false }],
    useIssueCaptchaChallengeMutation: () => [issue]
}));
// the real solver is covered in utils/captcha; here a proof is "solved" when we say so
const solving = vi.hoisted(() => ({ resolvers: [] as Array<(proof: string) => void>, instant: true }));
const solveLike = (c: { challenge: string }) => (solving.instant ? Promise.resolve(`proof-${c.challenge}`) : new Promise<string>((resolve) => solving.resolvers.push(resolve)));
vi.mock('@app/utils/captcha/solve', async (original) => ({
    ...((await original()) as object),
    solveChallenge: vi.fn()
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
const SEND = { en: 'Submit response', nl: 'Antwoorden versturen' } as const;
let n = 0;

function open(settings: Record<string, unknown>, preview = false) {
    store.dispatch(setWorkspace({ id: 'ws-1', workspaceName: 'acme' } as any));
    store.dispatch(setForm({ formId: `captcha-${++n}`, title: 'Survey', fields: [page('s1', 0, [text('a', 'Your name')])], settings } as any));
    function Page() {
        responder = useResponderState();
        return <FormSlide index={0} isPreviewMode={preview} />;
    }
    const view = render(
        <ReduxProvider store={store}>
            <Provider>
                <Page />
            </Provider>
        </ReduxProvider>
    );
    act(() => responder!.setResponderState({ ...responder!.responderState, currentSlide: 0, history: [] }));
    return view;
}
const type = async (value: string) => {
    act(() => void fireEvent.change(document.getElementById('input-field-a')!, { target: { value } }));
    await act(() => new Promise((resolve) => setTimeout(resolve, 350)));
};
const send = (lang: 'en' | 'nl') => act(async () => void fireEvent.click(screen.getByRole('button', { name: SEND[lang] })));
const header = (call: number) => submit.mock.calls[call][0].headers?.['X-BC-Captcha'];

describe('the automatic spam check on submit', () => {
    beforeEach(() => {
        window.PUBLIC_CONFIG = { HTTP_SCHEME: 'http://', FORM_DOMAIN: 'localhost:3000' } as any;
        Element.prototype.scrollIntoView = vi.fn();
        submit.mockReset();
        issue.mockReset();
        let counter = 0;
        issue.mockImplementation(async () => ({ data: { challenge: `c${++counter}`, algorithm: 'sha256-lz', bits: 17, subpuzzles: 8, expiresAt: 0 } }));
        submit.mockResolvedValue({ data: 'submission-1' });
        solving.instant = true;
        vi.mocked(solveChallenge).mockReset().mockImplementation(solveLike as any);
        solving.resolvers = [];
        resetCaptchaPasses();
        window.history.replaceState(null, '', '/acme/forms/f1?lang=en');
    });
    afterEach(() => vi.useRealTimers());

    it('does nothing on load and starts after the first interaction', async () => {
        open({ captchaRequired: true });
        await act(() => new Promise((resolve) => setTimeout(resolve, 50)));
        expect(issue).not.toHaveBeenCalled();
        await act(async () => void fireEvent.pointerDown(document.body));
        await act(() => new Promise((resolve) => setTimeout(resolve, 20)));
        expect(issue).toHaveBeenCalledTimes(1);
        expect(issue).toHaveBeenCalledWith(expect.objectContaining({ workspaceId: 'ws-1' }));
    });

    it('sends the proof in the X-BC-Captcha header, once per request', async () => {
        open({ captchaRequired: true });
        await type('Ada');
        await send('en');
        expect(submit).toHaveBeenCalledTimes(1);
        expect(header(0)).toMatch(/^proof-c\d$/);
        // the next proof is solved in the background straight after
        await act(() => new Promise((resolve) => setTimeout(resolve, 20)));
        expect(issue.mock.calls.length).toBeGreaterThanOrEqual(2);
    });

    it('asks for nothing and sends no header when the form does not require it', async () => {
        for (const settings of [{}, { captchaRequired: false }]) {
            submit.mockClear();
            open(settings);
            await type('Ada');
            await send('en');
            expect(submit).toHaveBeenCalledTimes(1);
            expect(submit.mock.calls[0][0].headers).toBeUndefined();
        }
        expect(issue).not.toHaveBeenCalled();
    });

    it('in the builder preview nothing is fetched, solved or sent', async () => {
        open({ captchaRequired: true }, true);
        await type('Ada');
        await send('en');
        expect(issue).not.toHaveBeenCalled();
        expect(submit).not.toHaveBeenCalled();
    });

    it('sends again once with a new proof after a refused one, and only then', async () => {
        submit.mockResolvedValueOnce({ error: { status: 422, data: { code: 'captcha_expired', message: 'x' } } }).mockResolvedValueOnce({ data: 'submission-2' });
        open({ captchaRequired: true });
        await type('Ada');
        await send('en');
        expect(submit).toHaveBeenCalledTimes(2);
        expect(header(0)).not.toBe(header(1));
        expect(header(1)).toBeTruthy();
    });

    it('does not keep retrying a refused proof', async () => {
        submit.mockResolvedValue({ error: { status: 422, data: { code: 'captcha_invalid', message: 'x' } } });
        open({ captchaRequired: true });
        await type('Ada');
        await send('en');
        expect(submit).toHaveBeenCalledTimes(2);
        expect((await screen.findByRole('alert')).textContent).toContain('could not be sent');
    });

    it.each([500, 503, 0])('never retries after a failure that may have stored the response (status %s)', async (status) => {
        submit.mockResolvedValue({ error: { status: status || 'FETCH_ERROR', data: { message: 'x' } } });
        open({ captchaRequired: true });
        await type('Ada');
        await send('en');
        expect(submit).toHaveBeenCalledTimes(1);
    });

    it('announces the wait politely only after 1.5 s, marks the button busy, and sends when ready', async () => {
        solving.instant = false;
        open({ captchaRequired: true });
        await type('Ada');
        vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] });
        const status = () => screen.getByTestId('captcha-status');
        await send('en');
        const button = screen.getByRole('button', { name: SEND.en });
        expect(status().getAttribute('role')).toBe('status');
        expect(status().getAttribute('aria-live')).toBe('polite');
        expect(status().textContent).toBe('');
        expect(submit).not.toHaveBeenCalled();
        await act(async () => void vi.advanceTimersByTime(1400));
        expect(status().textContent).toBe('');
        await act(async () => void vi.advanceTimersByTime(200));
        expect(status().textContent).toBe('Almost ready to send...');
        expect(button.getAttribute('aria-busy')).toBe('true');
        vi.useRealTimers();
        expect(await axeViolations(document, { page: false })).toEqual([]);
        // the proof arrives: the submit completes by itself
        await act(async () => solving.resolvers.forEach((resolve) => resolve('proof-late')));
        await act(() => new Promise((resolve) => setTimeout(resolve, 20)));
        expect(submit).toHaveBeenCalledTimes(1);
        expect(header(0)).toBe('proof-late');
        expect(status().textContent).toBe('');
    });

    it.each(['en', 'nl'] as const)('says what to do when the browser cannot do it (%s)', async (lang) => {
        window.history.replaceState(null, '', `/acme/forms/f1?lang=${lang}`);
        vi.mocked(solveChallenge).mockRejectedValue(new CaptchaUnavailable());
        open({ captchaRequired: true });
        await type('Ada');
        await send(lang);
        const message = {
            en: 'The automatic spam check did not work in this browser. Sign in with an email code, or try another browser.',
            nl: 'De automatische spamcontrole lukte niet in deze browser. Log in met een e-mailcode of probeer een andere browser.'
        }[lang];
        expect((await screen.findByRole('alert')).textContent).toBe(message);
        expect(submit).not.toHaveBeenCalled();
        expect(await axeViolations(document, { page: false })).toEqual([]);
    });

    it('says the wait in Dutch too', async () => {
        window.history.replaceState(null, '', '/acme/forms/f1?lang=nl');
        solving.instant = false;
        open({ captchaRequired: true });
        await type('Ada');
        vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] });
        await send('nl');
        await act(async () => void vi.advanceTimersByTime(1600));
        expect(screen.getByTestId('captcha-status').textContent).toBe('Bijna klaar om te versturen...');
    });
});
