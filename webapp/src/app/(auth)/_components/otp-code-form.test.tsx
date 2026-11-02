import React from 'react';

import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import '@app/shared/hocs/i18n-provider';

import OtpCodeForm from './otp-code-form';

const verifyMock = vi.fn();
const challengeMock = vi.fn();
const verifyMfaMock = vi.fn();
vi.mock('@app/store/auth/api', async (importOriginal) => {
    const actual: any = await importOriginal();
    return {
        ...actual,
        usePostVerifyOtpMutation: () => [verifyMock, { isLoading: false }],
        usePostSendOtpMutation: () => [vi.fn(), { isLoading: false }],
        usePostMfaChallengeMutation: () => [challengeMock, { isLoading: false }],
        useVerifyMfaMutation: () => [verifyMfaMock, { isLoading: false }]
    };
});
vi.mock('next/navigation', () => ({ useSearchParams: () => new URLSearchParams() }));
vi.mock('@app/components/modal-views/full-screen-modal-context', () => ({ useFullScreenModal: () => ({ closeModal: vi.fn() }) }));
vi.mock('@app/shadcn/components/ui/use-toast', () => ({ useToast: () => ({ toast: vi.fn() }) }));

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
