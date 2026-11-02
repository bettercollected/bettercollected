import React from 'react';

import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import '@app/shared/hocs/i18n-provider';
import { axeViolations } from '@app/test/axe';

import MfaCodeForm from './mfa-code-form';

const challengeMock = vi.fn();
const verifyMfaMock = vi.fn();
vi.mock('@app/store/auth/api', async (importOriginal) => {
    const actual: any = await importOriginal();
    return { ...actual, usePostMfaChallengeMutation: () => [challengeMock, { isLoading: false }], useVerifyMfaMutation: () => [verifyMfaMock, { isLoading: false }] };
});

const enter = (value: string) => fireEvent.change(screen.getByLabelText(/6-digit code|Recovery code/), { target: { value } });

describe('MfaCodeForm (the second step of signing in)', () => {
    beforeEach(() => {
        challengeMock.mockReset().mockResolvedValue({ data: { loggedIn: true } });
    });
    afterEach(() => {
        vi.useRealTimers();
    });

    it('asks for the code in a field the browser knows, focused', async () => {
        render(<MfaCodeForm onSignedIn={vi.fn()} onBack={vi.fn()} />);
        const input = screen.getByLabelText('6-digit code') as HTMLInputElement;
        expect(input.getAttribute('autocomplete')).toBe('one-time-code');
        expect(input.getAttribute('inputmode')).toBe('numeric');
        expect(document.activeElement).toBe(input);
        expect(screen.getByRole('heading', { name: 'Enter the code from your authenticator app' })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Sign in' })).toBeDisabled();
        expect(await axeViolations(document.body)).toEqual([]);
    });

    it('signs in with the code', async () => {
        const onSignedIn = vi.fn();
        render(<MfaCodeForm onSignedIn={onSignedIn} onBack={vi.fn()} />);
        enter('123 456');
        fireEvent.click(screen.getByRole('button', { name: 'Sign in' }));
        await waitFor(() => expect(onSignedIn).toHaveBeenCalled());
        expect(challengeMock).toHaveBeenCalledWith({ code: '123456' });
    });

    it('takes a recovery code from "Use a recovery code"', async () => {
        render(<MfaCodeForm onSignedIn={vi.fn()} onBack={vi.fn()} />);
        fireEvent.click(screen.getByRole('button', { name: 'Use a recovery code' }));
        expect(screen.getByLabelText('Recovery code').getAttribute('autocomplete')).toBe('off');
        enter('abcd-efgh-ijkl-mnop');
        fireEvent.click(screen.getByRole('button', { name: 'Sign in' }));
        await waitFor(() => expect(challengeMock).toHaveBeenCalledWith({ code: 'ABCD-EFGH-IJKL-MNOP' }));
        expect(await axeViolations(document.body)).toEqual([]);
    });

    it('says a wrong code is wrong, clears it and lets the person try again', async () => {
        challengeMock.mockResolvedValue({ error: { status: 422, data: { code: 'invalid_code' } } });
        render(<MfaCodeForm onSignedIn={vi.fn()} onBack={vi.fn()} />);
        enter('000000');
        fireEvent.click(screen.getByRole('button', { name: 'Sign in' }));
        expect(await screen.findByText('That code is not valid. Enter the code your app shows now.')).toBeInTheDocument();
        expect((screen.getByLabelText('6-digit code') as HTMLInputElement).value).toBe('');
        expect(screen.getByLabelText('6-digit code')).not.toBeDisabled();
        expect(await axeViolations(document.body)).toEqual([]);
    });

    it('shows the lock with its time and stays disabled until it ends', async () => {
        vi.useFakeTimers({ shouldAdvanceTime: true });
        challengeMock.mockResolvedValue({ error: { status: 429, data: { code: 'mfa_locked', retry_after: 840 } } });
        render(<MfaCodeForm onSignedIn={vi.fn()} onBack={vi.fn()} />);
        enter('000000');
        fireEvent.click(screen.getByRole('button', { name: 'Sign in' }));
        expect(await screen.findByText('Too many attempts. Try again in 14 minutes.')).toBeInTheDocument();
        expect(screen.getByRole('heading', { name: 'Too many attempts' })).toBeInTheDocument();
        expect(screen.getByLabelText('6-digit code')).toBeDisabled();
        expect(screen.getByRole('button', { name: 'Sign in' })).toBeDisabled();
        expect(await axeViolations(document.body)).toEqual([]);
        await act(async () => {
            vi.advanceTimersByTime(841_000);
        });
        expect(screen.getByLabelText('6-digit code')).not.toBeDisabled();
        expect(screen.queryByText(/Too many attempts. Try again/)).toBeNull();
    });

    it('sends the person back to the first step when the sign-in expired', async () => {
        challengeMock.mockResolvedValue({ error: { status: 401, data: { code: 'mfa_challenge_expired' } } });
        const onBack = vi.fn();
        render(<MfaCodeForm onSignedIn={vi.fn()} onBack={onBack} />);
        enter('123456');
        fireEvent.click(screen.getByRole('button', { name: 'Sign in' }));
        expect(await screen.findByText('Your sign-in has expired. Go back and sign in again.')).toBeInTheDocument();
        expect(screen.queryByLabelText('6-digit code')).toBeNull();
        expect(screen.queryByRole('button', { name: 'Sign in' })).toBeNull();
        expect(await axeViolations(document.body)).toEqual([]);
        fireEvent.click(screen.getByRole('button', { name: 'Back to sign in' }));
        expect(onBack).toHaveBeenCalled();
    });

    it('speaks formal Dutch to a browser that prefers it, outside the dashboard', async () => {
        const languages = vi.spyOn(window.navigator, 'languages', 'get').mockReturnValue(['nl-NL', 'en']);
        try {
            const { container } = render(<MfaCodeForm onSignedIn={vi.fn()} onBack={vi.fn()} />);
            expect(await screen.findByRole('heading', { name: 'Voer de code uit uw authenticator-app in' })).toBeInTheDocument();
            expect(screen.getByRole('button', { name: 'Gebruik een herstelcode' })).toBeInTheDocument();
            expect(screen.getByLabelText('6-cijferige code')).toBeInTheDocument();
            expect(container.querySelector('form')?.getAttribute('lang')).toBe('nl');
            expect(await axeViolations(document.body)).toEqual([]);
        } finally {
            languages.mockRestore();
        }
    });
});

describe('lock times', () => {
    it('says hours for the long locks that repeated lock-outs bring', async () => {
        const { mfaErrorText } = await import('./error-text');
        const t = (key: string, options?: { count?: number }) => `${key}:${options?.count}`;
        expect(mfaErrorText(t as any, { code: 'mfa_locked', retryAfter: 900 })).toBe('STAFF.MFA.ERRORS.LOCKED:15');
        expect(mfaErrorText(t as any, { code: 'mfa_locked', retryAfter: 3600 })).toBe('STAFF.MFA.ERRORS.LOCKED:60');
        expect(mfaErrorText(t as any, { code: 'mfa_locked', retryAfter: 6 * 3600 })).toBe('STAFF.MFA.ERRORS.LOCKED_HOURS:6');
        expect(mfaErrorText(t as any, { code: 'mfa_locked', retryAfter: 86400 })).toBe('STAFF.MFA.ERRORS.LOCKED_HOURS:24');
    });
});
