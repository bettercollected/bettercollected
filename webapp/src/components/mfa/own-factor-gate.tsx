'use client';

import React from 'react';

import { useTranslation } from 'react-i18next';

import TotpEnrolDialog from '@app/components/account-settings/totp-enrol-dialog';
import MfaCodeForm from '@app/components/mfa/mfa-code-form';
import { Dialog, DialogContent } from '@app/shadcn/components/ui/dialog';
import { useGetMfaStatusQuery, useLogoutMutation } from '@app/store/auth/api';
import { navigateTo } from '@app/utils/browser-navigation';

/**
 * What an owner is asked for when the server answers 409 `enrol_first`: before
 * the workspace rule is turned on, or before another member's authenticator app
 * is removed, the owner's own session must have used its own app. Someone who
 * has one enters its code (the session is promoted in place); someone who has
 * none sets one up. Then `onDone` runs, to try the action again; `onCancel`
 * leaves it.
 */
export default function OwnFactorGate({ onDone, onCancel }: { onDone: () => void; onCancel: () => void }) {
    const { t } = useTranslation();
    const { data: mine } = useGetMfaStatusQuery();
    const [logout] = useLogoutMutation();

    const signInAgain = async () => {
        await logout();
        navigateTo(`/login?redirect_to=${encodeURIComponent(window.location.pathname)}`);
    };

    if (!mine) return null;
    if (!mine.enabled) {
        return <TotpEnrolDialog onClose={onCancel} onSignInAgain={signInAgain} onEnrolled={onDone} />;
    }
    return (
        <Dialog open onOpenChange={(open) => !open && onCancel()}>
            <DialogContent className="max-w-md" title={t('STAFF.MFA.POLICY.FIRST_TITLE')}>
                <div className="flex flex-col gap-4 pr-6">
                    <MfaCodeForm session heading={t('STAFF.MFA.POLICY.FIRST_TITLE')} intro={t('STAFF.MFA.POLICY.FIRST_INTRO')} backLabel={t('STAFF.MFA.POLICY.CANCEL')} onBack={onCancel} onSignedIn={onDone} />
                </div>
            </DialogContent>
        </Dialog>
    );
}
