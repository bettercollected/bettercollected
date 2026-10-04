'use client';

import React, { useState } from 'react';

import { useSearchParams } from 'next/navigation';

import { KeyRound } from 'lucide-react';

import environments from '@app/configs/environments';
import { navigateWithReferrer, ssoEnabled, ssoErrorMessage } from '@app/lib/sso';
import { Button } from '@app/shadcn/components/ui/button';
import { Input } from '@app/shadcn/components/ui/input';

interface SsoSignInProps {
    // opens the form with this email (e.g. after an email code was refused
    // because the domain requires single sign-on)
    initialEmail?: string;
    notice?: string | null;
}

/**
 * "Sign in with SSO": the work email decides which workspace's identity
 * provider signs the user in (docs/sso.md). Off unless the build sets
 * NEXT_PUBLIC_ENABLE_SSO=true.
 */
export default function SsoSignIn({ initialEmail, notice }: SsoSignInProps) {
    const searchParams = useSearchParams();
    const errorMessage = ssoErrorMessage(searchParams?.get('sso_error'));
    const [open, setOpen] = useState(!!errorMessage || !!initialEmail);
    const [email, setEmail] = useState(initialEmail ?? '');

    if (!ssoEnabled) return null;

    const start = (e: React.FormEvent<HTMLFormElement>) => {
        e.preventDefault();
        const value = email.trim();
        if (!value) return;
        // a full navigation with the referrer, like the Google button, so
        // the backend can send the user back here (or on to the dashboard)
        navigateWithReferrer(`${environments.API_ENDPOINT_HOST}/auth/sso/login?${new URLSearchParams({ email: value }).toString()}`);
    };

    if (!open) {
        return (
            <Button type="button" variant="secondary" size="medium" className="w-full" onClick={() => setOpen(true)}>
                <KeyRound className="mr-2 h-4 w-4" aria-hidden="true" />
                Sign in with SSO
            </Button>
        );
    }

    return (
        <form className="flex w-full flex-col gap-3" onSubmit={start} aria-label="Sign in with SSO">
            <label htmlFor="sso-email" className="text-base font-semibold text-black-900">
                Work email
            </label>
            {notice && (
                <p role="status" className="body4 rounded-lg border border-[#F0D9B5] bg-[#FDF8EF] px-4 py-3 !text-black-800">
                    {notice}
                </p>
            )}
            <Input id="sso-email" type="email" required autoFocus placeholder="you@company.com" value={email} onChange={(e) => setEmail(e.target.value)} className="!text-base lg:!text-base" />
            {errorMessage && (
                <p role="alert" className="body4 !text-red-600">
                    {errorMessage}
                </p>
            )}
            <Button type="submit" variant="primary" size="medium" className="w-full">
                Continue with SSO
            </Button>
        </form>
    );
}
