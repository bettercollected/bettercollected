import React from 'react';

import { readFileSync } from 'fs';
import { resolve } from 'path';

import { fireEvent, render, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import OtpEmailForm from './otp-email-form';

let searchParams = new URLSearchParams();
vi.mock('next/navigation', () => ({ useSearchParams: () => searchParams }));

const sendOtp = vi.fn();
vi.mock('@app/store/auth/api', () => ({ usePostSendOtpMutation: () => [sendOtp, { isLoading: false }] }));
const toast = vi.hoisted(() => vi.fn());
vi.mock('@app/shadcn/components/ui/use-toast', () => ({ useToast: () => ({ toast }) }));
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
