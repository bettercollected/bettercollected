import React from 'react';

import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import SsoSignIn from '@app/app/(auth)/_components/sso-sign-in';
import { readRuntimeFlags } from '@app/lib/runtime-flags';
import RuntimeFlagsProvider from '@app/shared/hocs/runtime-flags-provider';

vi.mock('next/navigation', () => ({ useSearchParams: () => new URLSearchParams() }));

describe('readRuntimeFlags', () => {
    it.each(['true', 'TRUE', ' true ', '1', 'yes', 'on'])('SSO_ENABLED=%j turns single sign-on on', (value) => {
        expect(readRuntimeFlags({ SSO_ENABLED: value }).ssoEnabled).toBe(true);
    });

    it.each([undefined, '', 'false', '0', 'no', 'off', 'maybe'])('SSO_ENABLED=%j leaves it off', (value) => {
        expect(readRuntimeFlags({ SSO_ENABLED: value }).ssoEnabled).toBe(false);
    });

    it('ignores the old build-time NEXT_PUBLIC_ENABLE_SSO', () => {
        expect(readRuntimeFlags({ NEXT_PUBLIC_ENABLE_SSO: 'true' }).ssoEnabled).toBe(false);
    });
});

describe('the sign-in page follows the runtime flag', () => {
    const renderWith = (ssoEnabled?: boolean) =>
        render(
            ssoEnabled === undefined ? (
                <SsoSignIn />
            ) : (
                <RuntimeFlagsProvider flags={{ ssoEnabled }}>
                    <SsoSignIn />
                </RuntimeFlagsProvider>
            )
        );

    it('shows "Sign in with SSO" when the server says SSO is on', () => {
        renderWith(true);
        expect(screen.getByRole('button', { name: /sign in with sso/i })).toBeTruthy();
    });

    it.each([false, undefined])('hides it when SSO is off (flags: %s)', (flag) => {
        renderWith(flag as boolean | undefined);
        expect(screen.queryByRole('button', { name: /sign in with sso/i })).toBeNull();
    });
});
