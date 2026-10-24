import React from 'react';

import { fireEvent, render, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import OtpEmailForm from './otp-email-form';

let searchParams = new URLSearchParams();
vi.mock('next/navigation', () => ({ useSearchParams: () => searchParams }));

const sendOtp = vi.fn();
vi.mock('@app/store/auth/api', () => ({ usePostSendOtpMutation: () => [sendOtp, { isLoading: false }] }));
vi.mock('@app/shadcn/components/ui/use-toast', () => ({ useToast: () => ({ toast: vi.fn() }) }));
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

    it("leaves a respondent's code (sent through the workspace) as it was", async () => {
        searchParams = new URLSearchParams({ type: 'responder', workspace_id: 'ws-1' });
        submit('respondent@example.com');
        await waitFor(() => expect(sendOtp).toHaveBeenCalledWith({ receiver_email: 'respondent@example.com', workspace_id: 'ws-1' }));
    });
});
