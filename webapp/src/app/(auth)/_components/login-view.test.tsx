import React from 'react';

import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import '@app/shared/hocs/i18n-provider';

import LoginView from './login-view';

let searchParams = new URLSearchParams();
const replace = vi.fn();
vi.mock('next/navigation', () => ({ useSearchParams: () => searchParams, useRouter: () => ({ replace }) }));
vi.mock('@app/layouts/top-navbar-layout', () => ({ default: ({ children }: any) => <div>{children}</div> }));
vi.mock('@app/components/ui/logo', () => ({ default: () => null }));
vi.mock('./otp-email-form', () => ({ default: () => <p>email form</p> }));
vi.mock('./otp-code-form', () => ({ default: () => <p>otp form</p> }));

const challengeMock = vi.fn();
const verifyMfaMock = vi.fn();
vi.mock('@app/store/auth/api', async (importOriginal) => {
    const actual: any = await importOriginal();
    return { ...actual, usePostMfaChallengeMutation: () => [challengeMock, { isLoading: false }],
        useVerifyMfaMutation: () => [verifyMfaMock, { isLoading: false }] };
});

const assign = vi.fn();
vi.mock('@app/utils/browser-navigation', () => ({ reloadPage: vi.fn(), navigateTo: (path: string) => assign(path) }));

describe('LoginView after a provider sign-in that needs the second factor', () => {
    beforeEach(() => {
        challengeMock.mockReset().mockResolvedValue({ data: { loggedIn: true } });
        assign.mockReset();
        replace.mockReset();
    });

    it('asks for the first step as usual', () => {
        searchParams = new URLSearchParams();
        render(<LoginView />);
        expect(screen.getByText('email form')).toBeInTheDocument();
    });

    it('asks for the code at /login?mfa=1 and goes on to the page the sign-in came from', async () => {
        searchParams = new URLSearchParams({ mfa: '1', next: `${window.location.origin}/acme/dashboard/forms` });
        render(<LoginView />);
        expect(screen.queryByText('email form')).toBeNull();
        expect(screen.getByRole('heading', { name: 'One more step' })).toBeInTheDocument();
        fireEvent.change(screen.getByLabelText('6-digit code'), { target: { value: '123456' } });
        fireEvent.click(screen.getByRole('button', { name: 'Sign in' }));
        await waitFor(() => expect(assign).toHaveBeenCalledWith('/acme/dashboard/forms'));
    });

    it('never follows a next that leaves the site', async () => {
        searchParams = new URLSearchParams({ mfa: '1', next: 'https://evil.example/' });
        render(<LoginView />);
        fireEvent.change(screen.getByLabelText('6-digit code'), { target: { value: '123456' } });
        fireEvent.click(screen.getByRole('button', { name: 'Sign in' }));
        await waitFor(() => expect(assign).toHaveBeenCalledWith('/login'));
    });

    it.each(['%2F%2Fevil.com', '/%5Cevil.com', '/\\evil.com', '//evil.com', 'https:evil.com'])('falls back to the sign-in page for the next %j', async (hostile) => {
        searchParams = new URLSearchParams({ mfa: '1', next: hostile });
        render(<LoginView />);
        fireEvent.change(screen.getByLabelText('6-digit code'), { target: { value: '123456' } });
        fireEvent.click(screen.getByRole('button', { name: 'Sign in' }));
        await waitFor(() => expect(assign).toHaveBeenCalledWith('/login'));
    });

    it('speaks Dutch, footer and terms included, at the second step for a Dutch browser; the first step stays as it was', async () => {
        const languages = vi.spyOn(window.navigator, 'languages', 'get').mockReturnValue(['nl-NL', 'en']);
        try {
            searchParams = new URLSearchParams({ mfa: '1' });
            const { container } = render(<LoginView />);
            expect(await screen.findByText(/Door in te loggen, gaat u akkoord met onze/)).toBeInTheDocument();
            expect(screen.getByText('Privacybeleid')).toBeInTheDocument();
            expect(container.querySelector('footer')?.getAttribute('lang')).toBe('nl');
        } finally {
            languages.mockRestore();
        }
    });

    it('goes back to the plain sign-in page', () => {
        searchParams = new URLSearchParams({ mfa: '1' });
        render(<LoginView />);
        fireEvent.click(screen.getByRole('button', { name: 'Back to sign in' }));
        expect(replace).toHaveBeenCalledWith('/login');
    });
});
