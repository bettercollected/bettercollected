'use client';

import React, { useState } from 'react';

import { useSearchParams } from 'next/navigation';

import { KeyRound } from 'lucide-react';

import environments from '@app/configs/environments';
import { Button } from '@app/shadcn/components/ui/button';
import { Input } from '@app/shadcn/components/ui/input';

// Enterprise SSO through Polis (spike, docs/sso-spike.md). Off unless the
// build sets NEXT_PUBLIC_ENABLE_SSO=true.
export const ssoEnabled = process.env.NEXT_PUBLIC_ENABLE_SSO === 'true';

// The backend redirects back with a fixed code, never free text.
const ssoErrorMessages: Record<string, string> = {
    sso_disabled: 'Single sign-on is not enabled.',
    sso_not_configured: "Single sign-on isn't set up for this email domain. Sign in another way, or ask your workspace admin.",
    sso_email_domain_not_allowed: "Your identity provider signed you in with an email address this workspace's single sign-on doesn't cover.",
    sso_workspace_unavailable: 'The workspace for this sign-in is not available.',
    sso_expired: 'The sign-in took too long. Please try again.',
    sso_failed: 'Single sign-on failed. Please try again.'
};

export default function SsoSignIn({ isCreator, fromProPlan }: { isCreator: boolean; fromProPlan?: string | null }) {
    const searchParams = useSearchParams();
    const errorCode = searchParams?.get('sso_error');
    const [open, setOpen] = useState(!!errorCode);
    const [email, setEmail] = useState('');

    if (!ssoEnabled) return null;

    const start = (e: React.FormEvent<HTMLFormElement>) => {
        e.preventDefault();
        if (!email) return;
        const params = new URLSearchParams({ email: email.trim() });
        if (isCreator) params.set('creator', 'true');
        if (fromProPlan) params.set('prospective_pro_user', 'true');
        // Navigate with a full referrer, like the Google button, so the
        // backend can send the user back here (or on to the dashboard).
        const link = document.createElement('a');
        link.href = `${environments.API_ENDPOINT_HOST}/auth/sso/login?${params.toString()}`;
        link.referrerPolicy = 'unsafe-url';
        document.body.appendChild(link);
        link.click();
        link.remove();
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
            <Input id="sso-email" type="email" required autoFocus placeholder="you@company.com" value={email} onChange={(e) => setEmail(e.target.value)} className="!text-base lg:!text-base" />
            {errorCode && (
                <p role="alert" className="body4 !text-red-600">
                    {ssoErrorMessages[errorCode] ?? ssoErrorMessages.sso_failed}
                </p>
            )}
            <Button type="submit" variant="primary" size="medium" className="w-full">
                Continue with SSO
            </Button>
        </form>
    );
}
