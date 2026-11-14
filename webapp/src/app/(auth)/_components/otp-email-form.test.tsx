import React from 'react';

import { readFileSync } from 'fs';
import { resolve } from 'path';

import { fireEvent, render, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { resetMailProofKnowledge } from '@app/utils/captcha/mail-proof';

import OtpEmailForm from './otp-email-form';

let searchParams = new URLSearchParams();
vi.mock('next/navigation', () => ({ useSearchParams: () => searchParams }));

const sendOtp = vi.fn();
vi.mock('@app/store/auth/api', () => ({ usePostSendOtpMutation: () => [sendOtp, { isLoading: false }] }));
const toast = vi.hoisted(() => vi.fn());
vi.mock('@app/shadcn/components/ui/use-toast', () => ({ useToast: () => ({ toast }) }));
// the spam check's challenge route, and the proofs it solves (utils/captcha): nothing is solved in these tests
const issueChallenge = vi.hoisted(() => vi.fn());
vi.mock('@app/store/redux/form-api', () => ({ useIssueMailChallengeMutation: () => [issueChallenge] }));
const take = vi.hoisted(() => vi.fn());
vi.mock('@app/utils/captcha/captcha-pass', async (importOriginal) => ({ ...((await importOriginal()) as object), captchaPassFor: () => ({ take }) }));
vi.mock('@Components/login/login-with-google-button', () => ({ default: () => null }));

const submit = (email: string) => {
    render(<OtpEmailForm setEmail={vi.fn()} />);
    const input = document.querySelector('input[type="email"]') as HTMLInputElement;
    fireEvent.change(input, { target: { value: email } });
    fireEvent.submit(input.closest('form') as HTMLFormElement);
};

describe('sign-in code mail language', () => {
    beforeEach(() => {
        sendOtp.mockReset();
        sendOtp.mockResolvedValue({ data: { message: 'sent' } });
        vi.spyOn(window.navigator, 'languages', 'get').mockReturnValue(['nl-NL', 'en']);
    });
    afterEach(() => vi.restoreAllMocks());

    it("asks for the creator's code in the browser's language", async () => {
        searchParams = new URLSearchParams();
        submit('maker@example.com');
        await waitFor(() => expect(sendOtp).toHaveBeenCalledWith({ receiver_email: 'maker@example.com', workspace_id: '', locale: 'nl' }));
    });

    it("asks for a respondent's code (sent through the workspace) in the respondent's language", async () => {
        searchParams = new URLSearchParams({ type: 'responder', workspace_id: 'ws-1' });
        submit('respondent@example.com');
        await waitFor(() => expect(sendOtp).toHaveBeenCalledWith({ receiver_email: 'respondent@example.com', workspace_id: 'ws-1', locale: 'nl' }));
    });

    it("follows the language the respondent's link chose over the browser's", async () => {
        window.history.replaceState(null, '', '/login?type=responder&workspace_id=ws-1&lang=en');
        searchParams = new URLSearchParams({ type: 'responder', workspace_id: 'ws-1', lang: 'en' });
        try {
            submit('respondent@example.com');
            await waitFor(() => expect(sendOtp).toHaveBeenCalledWith({ receiver_email: 'respondent@example.com', workspace_id: 'ws-1', locale: 'en' }));
        } finally {
            window.history.replaceState(null, '', '/');
        }
    });
});

describe('sign-in code mail refused as too many (429)', () => {
    beforeEach(() => {
        toast.mockReset();
        sendOtp.mockReset();
        searchParams = new URLSearchParams();
    });
    afterEach(() => vi.restoreAllMocks());

    it('says so, the same for every address, and does not take it for a failure to send', async () => {
        for (const address of ['known@example.com', 'nobody@example.com']) {
            sendOtp.mockResolvedValue({ error: { status: 429, data: { code: 'rate_limited', message: 'x', retry_after: 600 } } });
            submit(address);
            await waitFor(() => expect(toast).toHaveBeenCalled());
        }
        const messages = toast.mock.calls.map(([arg]) => arg);
        expect(messages).toHaveLength(2);
        expect(messages[0]).toEqual(messages[1]);
        expect(messages[0]).toEqual({ description: 'Too many codes were requested for this email address or from this network. Please wait a while (up to an hour) and try again.', variant: 'destructive' });
    });

    it('still says it failed for another error', async () => {
        sendOtp.mockResolvedValue({ error: { status: 502, data: { code: 'code_mail_failed' } } });
        submit('known@example.com');
        await waitFor(() => expect(toast).toHaveBeenCalledWith({ description: 'Failed to send OTP', variant: 'destructive' }));
    });

    it('has the message in English and Dutch', () => {
        for (const [lang, start] of [
            ['en', 'Too many codes'],
            ['nl', 'Er zijn te veel codes']
        ]) {
            const common = JSON.parse(readFileSync(resolve(__dirname, `../../../../public/locales/${lang}/common.json`), 'utf8'));
            expect(common.RESPONDER_SECTION.OTP_RATE_LIMITED.startsWith(start)).toBe(true);
        }
    });
});


describe('the automatic spam check before the code mail', () => {
    const missing = { error: { status: 422, data: { code: 'captcha_missing', message: 'x' } } };
    beforeEach(() => {
        toast.mockReset();
        sendOtp.mockReset();
        take.mockReset();
        issueChallenge.mockReset();
        resetMailProofKnowledge();
        searchParams = new URLSearchParams();
    });
    afterEach(() => vi.restoreAllMocks());

    it('asks for nothing while the server does not: one request, no proof, no challenge', async () => {
        sendOtp.mockResolvedValue({ data: { message: 'sent' } });
        submit('maker@example.com');
        await waitFor(() => expect(sendOtp).toHaveBeenCalledTimes(1));
        expect(sendOtp.mock.calls[0][0]).not.toHaveProperty('headers');
        expect(take).not.toHaveBeenCalled();
        expect(issueChallenge).not.toHaveBeenCalled();
    });

    it("solves a proof and sends again, once, when the server asks for one (the creator's code has no workspace)", async () => {
        sendOtp.mockResolvedValueOnce(missing).mockResolvedValueOnce({ data: { message: 'sent' } });
        take.mockResolvedValue('PROOF-1');
        submit('maker@example.com');
        await waitFor(() => expect(sendOtp).toHaveBeenCalledTimes(2));
        expect(sendOtp.mock.calls[0][0]).not.toHaveProperty('headers');
        expect(sendOtp.mock.calls[1][0]).toMatchObject({ receiver_email: 'maker@example.com', workspace_id: '', headers: { 'X-BC-Captcha': 'PROOF-1' } });
        expect(take).toHaveBeenCalledWith(expect.any(Function), expect.objectContaining({ fresh: true }));
        expect(toast).toHaveBeenCalledWith({ description: 'OTP sent successfully' });
    });

    it('sends the proof of a respondent for the workspace of the link', async () => {
        searchParams = new URLSearchParams({ type: 'responder', workspace_id: 'ws-1' });
        sendOtp.mockResolvedValueOnce(missing).mockResolvedValueOnce({ data: { message: 'sent' } });
        take.mockResolvedValue('PROOF-2');
        submit('respondent@example.com');
        await waitFor(() => expect(sendOtp).toHaveBeenCalledTimes(2));
        expect(sendOtp.mock.calls[1][0]).toMatchObject({ workspace_id: 'ws-1', headers: { 'X-BC-Captcha': 'PROOF-2' } });
    });

    it('says so when the browser cannot calculate the proof, and sends nothing more', async () => {
        sendOtp.mockResolvedValue(missing);
        take.mockRejectedValue(new Error('no'));
        submit('maker@example.com');
        await waitFor(() => expect(toast).toHaveBeenCalledWith({ description: expect.stringMatching(/spam check did not work/i), variant: 'destructive' }));
        expect(sendOtp).toHaveBeenCalledTimes(1);
    });

    it('has the messages in English and Dutch', () => {
        for (const lang of ['en', 'nl']) {
            const common = JSON.parse(readFileSync(resolve(__dirname, `../../../../public/locales/${lang}/common.json`), 'utf8'));
            expect(common.RESPONDER_SECTION.OTP_CAPTCHA_FAILED).toBeTruthy();
            expect(common.RESPONDER_SECTION.OTP_CAPTCHA_WAITING).toBeTruthy();
        }
    });
});


describe('sign-in code mail when the server cannot count requests (503)', () => {
    const unavailable = (data: Record<string, unknown> = {}) => ({ error: { status: 503, data: { code: 'rate_limiter_unavailable', retry_after: 60, ...data } } });
    beforeEach(() => {
        toast.mockReset();
        sendOtp.mockReset();
        searchParams = new URLSearchParams();
    });
    afterEach(() => vi.restoreAllMocks());

    it("shows the server's own message, which speaks the language of the request, not the generic failure", async () => {
        sendOtp.mockResolvedValue(unavailable({ message: 'Inlogcodes zijn tijdelijk niet beschikbaar. Probeer het over een minuut opnieuw.' }));
        submit('known@example.com');
        await waitFor(() => expect(toast).toHaveBeenCalledWith({ description: 'Inlogcodes zijn tijdelijk niet beschikbaar. Probeer het over een minuut opnieuw.', variant: 'destructive' }));
        expect(sendOtp).toHaveBeenCalledTimes(1);
    });

    it('says it in the page language, with the wait from Retry-After, when the answer carries no message', async () => {
        sendOtp.mockResolvedValue(unavailable({ retry_after: 90 }));
        submit('known@example.com');
        await waitFor(() => expect(toast).toHaveBeenCalledWith({ description: 'Sign-in codes are temporarily unavailable. Please try again in 90 seconds.', variant: 'destructive' }));
    });

    it('falls back to a minute when the wait is missing or nonsense, and is not the 429 or the generic failure', async () => {
        sendOtp.mockResolvedValue(unavailable({ retry_after: 'soon' }));
        submit('known@example.com');
        await waitFor(() => expect(toast).toHaveBeenCalledWith({ description: 'Sign-in codes are temporarily unavailable. Please try again in 60 seconds.', variant: 'destructive' }));
        const text = toast.mock.calls.map(([arg]) => arg.description).join(' ');
        expect(text).not.toMatch(/Too many codes|Failed to send OTP/);
    });

    it('still takes any other 503 for a failure to send', async () => {
        sendOtp.mockResolvedValue({ error: { status: 503, data: { code: 'code_mail_failed' } } });
        submit('known@example.com');
        await waitFor(() => expect(toast).toHaveBeenCalledWith({ description: 'Failed to send OTP', variant: 'destructive' }));
    });

    it('has the message in English and Dutch with the same placeholder', () => {
        for (const lang of ['en', 'nl']) {
            const common = JSON.parse(readFileSync(resolve(__dirname, `../../../../public/locales/${lang}/common.json`), 'utf8'));
            expect(common.RESPONDER_SECTION.OTP_UNAVAILABLE).toContain('{{seconds}}');
        }
    });
});
