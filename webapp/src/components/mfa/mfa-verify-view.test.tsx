import React from 'react';

import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import '@app/shared/hocs/i18n-provider';
import { axeViolations } from '@app/test/axe';

import MfaVerifyView, { verifiedDestination } from './mfa-verify-view';

const status: { data: any; isLoading: boolean; isError: boolean } = { data: undefined, isLoading: false, isError: false };
const verifyMock = vi.fn();
vi.mock('@app/store/auth/api', async (importOriginal) => {
    const actual: any = await importOriginal();
    return {
        ...actual,
        useGetMfaStatusQuery: () => status,
        useLogoutMutation: () => [vi.fn()],
        useVerifyMfaMutation: () => [verifyMock, { isLoading: false }],
        usePostMfaChallengeMutation: () => [vi.fn(), { isLoading: false }],
        useStartTotpEnrolmentMutation: () => [vi.fn().mockResolvedValue({ data: { factorId: 'f1', secret: 'AAAA BBBB', uri: 'otpauth://totp/x?secret=AAAABBBB' } }), { reset: vi.fn() }],
        useConfirmTotpEnrolmentMutation: () => [vi.fn(), { isLoading: false, reset: vi.fn() }]
    };
});
const go = vi.fn();
vi.mock('@app/utils/browser-navigation', () => ({ navigateTo: (path: string) => go(path), reloadPage: vi.fn() }));

describe('MfaVerifyView (a workspace requires the second factor)', () => {
    beforeEach(() => {
        go.mockReset();
        verifyMock.mockReset().mockResolvedValue({ data: { available: true, enabled: true } });
        status.data = { available: true, enabled: true, recoveryLeft: 8 };
        status.isLoading = false;
        status.isError = false;
    });

    it('asks a person with an app for the code, promotes the same session and goes back to the page', async () => {
        render(<MfaVerifyView workspaceName="acme" next="/acme/dashboard/forms?x=1" />);
        expect(screen.getByRole('heading', { name: 'This workspace needs your second step' })).toBeInTheDocument();
        expect(await axeViolations(document.body)).toEqual([]);
        fireEvent.change(screen.getByLabelText('6-digit code'), { target: { value: '123456' } });
        fireEvent.click(screen.getByRole('button', { name: 'Continue' }));
        await waitFor(() => expect(verifyMock).toHaveBeenCalledWith({ code: '123456' }));
        await waitFor(() => expect(go).toHaveBeenCalledWith('/acme/dashboard/forms?x=1'));
    });

    it('offers the setup to a person without an app', async () => {
        status.data = { available: true, enabled: false };
        render(<MfaVerifyView workspaceName="acme" />);
        expect(screen.getByRole('heading', { name: 'This workspace requires an authenticator app' })).toBeInTheDocument();
        expect(await axeViolations(document.body)).toEqual([]);
        fireEvent.click(screen.getByRole('button', { name: 'Set up an authenticator app' }));
        expect(await screen.findByText('Scan the QR code')).toBeInTheDocument();
    });

    it('lets the person through when the server no longer asks', () => {
        status.data = { available: false, enabled: false };
        render(<MfaVerifyView workspaceName="acme" />);
        fireEvent.click(screen.getByRole('button', { name: 'Continue' }));
        expect(go).toHaveBeenCalledWith('/acme/dashboard');
    });

    it('only goes back to a dashboard page of this workspace', () => {
        expect(verifiedDestination('acme', '/acme/dashboard/forms')).toBe('/acme/dashboard/forms');
        expect(verifiedDestination('acme', '/other/dashboard')).toBe('/acme/dashboard');
        expect(verifiedDestination('acme', 'https://evil.example/acme/dashboard')).toBe('/acme/dashboard');
        expect(verifiedDestination('acme', '//evil.example')).toBe('/acme/dashboard');
        expect(verifiedDestination('acme', undefined)).toBe('/acme/dashboard');
        expect(verifiedDestination('acme', '/acme/dashboardx')).toBe('/acme/dashboard');
    });
});
