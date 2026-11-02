'use client';

import React, { useState } from 'react';

import { useTranslation } from 'react-i18next';

import TotpEnrolDialog from '@app/components/account-settings/totp-enrol-dialog';
import MfaCodeForm from '@app/components/mfa/mfa-code-form';
import { Button } from '@app/shadcn/components/ui/button';
import { useGetMfaStatusQuery, useLogoutMutation } from '@app/store/auth/api';
import { navigateTo } from '@app/utils/browser-navigation';
import { safeNextPath } from '@app/utils/mfa';

/** Where to go once the session meets the workspace's rule: the page it was on (a dashboard page of this workspace), else the dashboard. */
export function verifiedDestination(workspaceName: string, next: string | undefined): string {
    const dashboard = `/${encodeURIComponent(workspaceName)}/dashboard`;
    const path = safeNextPath(next);
    return path && (path === dashboard || path.startsWith(`${dashboard}/`) || path.startsWith(`${dashboard}?`)) ? path : dashboard;
}

/**
 * What a signed-in person sees when a workspace requires an authenticator app
 * and this session has not presented one (403 `mfa_required`): the code step
 * for someone who has an app, or the setup for someone who has none. Nobody is
 * signed out: the same session is promoted and the page carries on.
 */
export default function MfaVerifyView({ workspaceName, next }: { workspaceName: string; next?: string }) {
    const { t } = useTranslation();
    const { data: status, isLoading, isError } = useGetMfaStatusQuery();
    const [logout] = useLogoutMutation();
    const [enrolling, setEnrolling] = useState(false);
    const destination = verifiedDestination(workspaceName, next);
    const go = () => navigateTo(destination);

    const signInAgain = async () => {
        await logout();
        navigateTo(`/login?redirect_to=${encodeURIComponent(destination)}`);
    };

    return (
        <main className="mx-auto flex w-full max-w-[460px] flex-col gap-5 px-5 py-12">
            {isLoading && <p className="text-sm text-black-700">{t('STAFF.MFA.VERIFY.LOADING')}</p>}
            {isError && (
                <p role="alert" className="text-sm text-black-800">
                    {t('STAFF.MFA.ERRORS.GENERIC')}
                </p>
            )}
            {status && !status.available && (
                // the server's switch is off: nothing is required any more
                <>
                    <p className="text-sm text-black-800">{t('STAFF.MFA.VERIFY.NOT_NEEDED')}</p>
                    <Button type="button" onClick={go}>
                        {t('STAFF.MFA.VERIFY.CONTINUE')}
                    </Button>
                </>
            )}
            {status?.available && status.enabled && <MfaCodeForm session onSignedIn={go} onBack={() => navigateTo('/workspace/select')} />}
            {status?.available && !status.enabled && (
                <>
                    <h1 className="text-base font-semibold text-black-900">{t('STAFF.MFA.VERIFY.SETUP_TITLE')}</h1>
                    <p className="text-sm leading-relaxed text-black-700">{t('STAFF.MFA.VERIFY.SETUP_INTRO')}</p>
                    <div className="flex flex-col gap-3">
                        <Button type="button" onClick={() => setEnrolling(true)}>
                            {t('STAFF.MFA.CARD.SET_UP')}
                        </Button>
                        <Button type="button" variant="ghost" onClick={() => navigateTo('/workspace/select')}>
                            {t('STAFF.MFA.VERIFY.BACK')}
                        </Button>
                    </div>
                    {enrolling && <TotpEnrolDialog onClose={() => setEnrolling(false)} onSignInAgain={signInAgain} onEnrolled={go} />}
                </>
            )}
        </main>
    );
}
