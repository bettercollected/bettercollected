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
vi.mock('./otp-email-form', () => ({
    default: ({ card, setEmail }: any) => (
        <button type="button" data-card={String(!!card)} onClick={() => setEmail('ada@example.test')}>
            email form
        </button>
    )
}));
vi.mock('./otp-code-form', () => ({ default: ({ card }: any) => <p data-card={String(!!card)}>otp form</p> }));

const challengeMock = vi.fn();
const verifyMfaMock = vi.fn();
vi.mock('@app/store/auth/api', async (importOriginal) => {
    const actual: any = await importOriginal();
    return { ...actual, usePostMfaChallengeMutation: () => [challengeMock, { isLoading: false }], useVerifyMfaMutation: () => [verifyMfaMock, { isLoading: false }] };
});

const assign = vi.fn();
vi.mock('@app/utils/browser-navigation', () => ({ reloadPage: vi.fn(), navigateTo: (path: string) => assign(path) }));

describe('which sign-in wears the app theme', () => {
    it("the creator's sign-in carries the theme attribute", () => {
        searchParams = new URLSearchParams();
        const { container } = render(<LoginView />);
        expect(container.querySelector('[data-app-theme="daybreak"]')).not.toBeNull();
    });

    it("the respondent's sign-in (?type=responder, also served on custom domains) does not: it keeps paper mist", () => {
        searchParams = new URLSearchParams({ type: 'responder' });
        const { container } = render(<LoginView />);
        expect(screen.getByRole('heading', { name: 'See your submissions' })).toBeInTheDocument();
        expect(container.querySelector('[data-app-theme]')).toBeNull();
    });
});

describe("the creator's sign-in: one card on the canvas", () => {
    it('has one page heading, the welcome, in a card with the motif once and the form inside', () => {
        searchParams = new URLSearchParams();
        const { container } = render(<LoginView />);
        const headings = screen.getAllByRole('heading');
        expect(headings).toHaveLength(1);
        expect(headings[0]).toHaveTextContent('Welcome back');
        const card = screen.getByRole('region', { name: 'Welcome back' });
        expect(card).toContainElement(screen.getByText('email form'));
        expect(screen.getByText('email form')).toHaveAttribute('data-card', 'true');
        expect(container.querySelectorAll('svg[aria-hidden="true"][viewBox="-360 0 1000 148"]')).toHaveLength(1);
        expect(card).toHaveClass('bg-surface', 'border-hairline-strong');
    });

    it('says nothing about the product: no pitch, no bullets, no claims, no hand-picked colour', () => {
        searchParams = new URLSearchParams();
        const { container } = render(<LoginView />);
        const text = container.textContent ?? '';
        expect(text).not.toMatch(/custom domain|trust footer|on a site you own|privacy-first|Pro\b/i);
        expect(container.querySelector('ul')).toBeNull();
        expect(container.innerHTML).not.toMatch(/#[0-9a-fA-F]{6}/);
    });

    it('names the code step "Check your email", and the sign-up "Sign Up"', () => {
        searchParams = new URLSearchParams();
        const { unmount } = render(<LoginView />);
        fireEvent.click(screen.getByText('email form'));
        expect(screen.getByRole('heading', { name: 'Check your email' })).toBeInTheDocument();
        expect(screen.getByText('otp form')).toHaveAttribute('data-card', 'true');
        unmount();
        searchParams = new URLSearchParams({ isSignup: 'true' });
        render(<LoginView />);
        expect(screen.getByRole('heading', { name: 'Sign Up' })).toBeInTheDocument();
    });

    it("keeps one h1 at the second factor, with the code form's own h2 under it", () => {
        searchParams = new URLSearchParams({ mfa: '1' });
        render(<LoginView />);
        expect(screen.getByRole('heading', { level: 1, name: 'One more step' })).toBeInTheDocument();
        expect(screen.getByRole('heading', { level: 2, name: 'Enter the code from your authenticator app' })).toBeInTheDocument();
    });
});

describe("the respondent's sign-in stays as it was", () => {
    it('keeps its pitch panel, no card and the plain forms', () => {
        searchParams = new URLSearchParams({ type: 'responder' });
        const { container } = render(<LoginView />);
        expect(screen.getByRole('heading', { name: 'See your submissions' })).toBeInTheDocument();
        expect(screen.getByText("Verify your email to see every response you've submitted to this workspace — and request deletion of any of them.")).toBeInTheDocument();
        expect(screen.getByText('email form')).toHaveAttribute('data-card', 'false');
        expect(screen.queryByRole('region')).toBeNull();
        expect(container.querySelector('svg[viewBox="-360 0 1000 148"]')).toBeNull();
    });
});

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
