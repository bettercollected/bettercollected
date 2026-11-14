import React from 'react';

import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import '@app/shared/hocs/i18n-provider';

import OtpCodeForm from './otp-code-form';

const verifyMock = vi.fn();
const sendMock = vi.hoisted(() => vi.fn());
const toast = vi.hoisted(() => vi.fn());
const challengeMock = vi.fn();
const verifyMfaMock = vi.fn();
vi.mock('@app/store/auth/api', async (importOriginal) => {
    const actual: any = await importOriginal();
    return {
        ...actual,
        usePostVerifyOtpMutation: () => [verifyMock, { isLoading: false }],
        usePostSendOtpMutation: () => [sendMock, { isLoading: false }],
        usePostMfaChallengeMutation: () => [challengeMock, { isLoading: false }],
        useVerifyMfaMutation: () => [verifyMfaMock, { isLoading: false }]
    };
});
vi.mock('@app/store/redux/form-api', () => ({ useIssueMailChallengeMutation: () => [vi.fn()] }));
vi.mock('next/navigation', () => ({ useSearchParams: () => new URLSearchParams() }));
vi.mock('@app/components/modal-views/full-screen-modal-context', () => ({ useFullScreenModal: () => ({ closeModal: vi.fn() }) }));
vi.mock('@app/shadcn/components/ui/use-toast', () => ({ useToast: () => ({ toast }) }));

const reload = vi.fn();
vi.mock('@app/utils/browser-navigation', () => ({ reloadPage: () => reload(), navigateTo: vi.fn() }));

describe('OtpCodeForm with an account that has an authenticator app', () => {
    beforeEach(() => {
        verifyMock.mockReset();
        challengeMock.mockReset().mockResolvedValue({ data: { loggedIn: true } });
        reload.mockReset();
    });

    const enterEmailCode = () => {
        fireEvent.change(screen.getByPlaceholderText('eg: 000000'), { target: { value: '123456' } });
        fireEvent.click(screen.getByRole('button', { name: /sign in/i }));
    };

    it('does not finish the sign-in at the email code: it asks for the second factor', async () => {
        verifyMock.mockResolvedValue({ data: { mfaRequired: true } });
        const onMfaChange = vi.fn();
        render(<OtpCodeForm email="maker@example.org" setEmail={vi.fn()} onMfaChange={onMfaChange} />);
        enterEmailCode();
        expect(await screen.findByLabelText('6-digit code')).toBeInTheDocument();
        expect(onMfaChange).toHaveBeenCalledWith(true);
        expect(reload).not.toHaveBeenCalled();
    });

    it('finishes after the second factor, and going back returns to the email step', async () => {
        verifyMock.mockResolvedValue({ data: { mfaRequired: true } });
        const setEmail = vi.fn();
        const onMfaChange = vi.fn();
        render(<OtpCodeForm email="maker@example.org" setEmail={setEmail} onMfaChange={onMfaChange} />);
        enterEmailCode();
        fireEvent.change(await screen.findByLabelText('6-digit code'), { target: { value: '654321' } });
        fireEvent.click(screen.getByRole('button', { name: 'Sign in' }));
        await waitFor(() => expect(reload).toHaveBeenCalled());
        expect(challengeMock).toHaveBeenCalledWith({ code: '654321' });

        fireEvent.click(screen.getByRole('button', { name: 'Back to sign in' }));
        expect(onMfaChange).toHaveBeenLastCalledWith(false);
        expect(setEmail).toHaveBeenCalledWith('');
    });

    it('still signs in at once for an account without one', async () => {
        verifyMock.mockResolvedValue({ data: { access_token: 'x' } });
        render(<OtpCodeForm email="maker@example.org" setEmail={vi.fn()} />);
        enterEmailCode();
        await waitFor(() => expect(reload).toHaveBeenCalled());
        expect(screen.queryByLabelText('6-digit code')).toBeNull();
    });
});

describe('OtpCodeForm resending a code', () => {
    beforeEach(() => {
        sendMock.mockReset();
        toast.mockReset();
        vi.useFakeTimers({ shouldAdvanceTime: true });
    });
    afterEach(() => vi.useRealTimers());

    const resend = async () => {
        render(<OtpCodeForm email="maker@example.org" setEmail={vi.fn()} />);
        for (let second = 0; second < 61; second++) await act(async () => void vi.advanceTimersByTime(1000));
        fireEvent.click(screen.getByText(/resend/i));
    };

    it('says so when the server refuses it as too many (429)', async () => {
        sendMock.mockResolvedValue({ error: { status: 429, data: { code: 'rate_limited', message: 'x', retry_after: 900 } } });
        await resend();
        await waitFor(() => expect(toast).toHaveBeenCalledWith({ description: expect.stringMatching(/too many codes/i), variant: 'destructive' }));
    });

    it('says the code could not be sent (503), with the server wait, and keeps Resend closed for that long', async () => {
        sendMock.mockResolvedValue({ error: { status: 503, data: { code: 'rate_limiter_unavailable', retry_after: 45 } } });
        await resend();
        await waitFor(() => expect(toast).toHaveBeenCalledWith({ description: 'Sign-in codes are temporarily unavailable. Please try again in 45 seconds.', variant: 'destructive' }));
        expect(screen.getByText(/resend \(45s\)/i)).toBeTruthy();
        expect(sendMock).toHaveBeenCalledTimes(1);
    });

    it('is a real button, closed (disabled and aria-disabled) during the wait and open after it', async () => {
        render(<OtpCodeForm email="maker@example.org" setEmail={vi.fn()} />);
        const closed = screen.getByRole('button', { name: /resend \(60s\)/i }) as HTMLButtonElement;
        expect(closed.tagName).toBe('BUTTON');
        expect(closed.type).toBe('button');
        expect(closed.disabled).toBe(true);
        expect(closed.getAttribute('aria-disabled')).toBe('true');
        fireEvent.click(closed);
        expect(sendMock).not.toHaveBeenCalled();
        for (let second = 0; second < 61; second++) await act(async () => void vi.advanceTimersByTime(1000));
        const open = screen.getByRole('button', { name: /^resend$/i }) as HTMLButtonElement;
        expect(open.disabled).toBe(false);
        expect(open.getAttribute('aria-disabled')).toBe('false');
    });

    it('sends one mail for a double click, and keeps Resend closed while it is under way', async () => {
        let finish: (value: unknown) => void = () => {};
        sendMock.mockReturnValue(new Promise((resolve) => (finish = resolve)));
        render(<OtpCodeForm email="maker@example.org" setEmail={vi.fn()} />);
        for (let second = 0; second < 61; second++) await act(async () => void vi.advanceTimersByTime(1000));
        const resendButton = screen.getByRole('button', { name: /^resend$/i }) as HTMLButtonElement;
        fireEvent.click(resendButton);
        fireEvent.click(resendButton);
        await waitFor(() => expect(sendMock).toHaveBeenCalledTimes(1));
        await waitFor(() => expect((screen.getByRole('button', { name: /^resend$/i }) as HTMLButtonElement).disabled).toBe(true));
        expect(screen.getByRole('button', { name: /^resend$/i }).getAttribute('aria-busy')).toBe('true');
        finish({ data: { message: 'sent' } });
        await waitFor(() => expect(screen.getByRole('button', { name: /resend \(60s\)/i })).toBeTruthy());
        expect(sendMock).toHaveBeenCalledTimes(1);
    });

    it('says nothing new for a code that was sent', async () => {
        sendMock.mockResolvedValue({ data: { message: 'sent' } });
        await resend();
        await waitFor(() => expect(sendMock).toHaveBeenCalled());
        expect(toast).not.toHaveBeenCalled();
    });
});
