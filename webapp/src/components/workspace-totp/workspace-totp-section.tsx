'use client';

import React, { useState } from 'react';

import { useTranslation } from 'react-i18next';

import TotpEnrolDialog from '@app/components/account-settings/totp-enrol-dialog';
import { mfaErrorText } from '@app/components/mfa/error-text';
import MfaCodeForm from '@app/components/mfa/mfa-code-form';
import { useWorkspacePermissions } from '@app/lib/hooks/use-workspace-permissions';
import { WorkspacePermission } from '@app/models/enums/workspace-permission';
import { Button } from '@app/shadcn/components/ui/button';
import { Dialog, DialogContent } from '@app/shadcn/components/ui/dialog';
import { useToast } from '@app/shadcn/components/ui/use-toast';
import { useGetMfaStatusQuery, useLogoutMutation } from '@app/store/auth/api';
import { useAppSelector } from '@app/store/hooks';
import { useGetWorkspaceTotpPolicyQuery, useSetWorkspaceTotpPolicyMutation } from '@app/store/workspaces/api';
import { navigateTo } from '@app/utils/browser-navigation';
import { mfaFailureOf } from '@app/utils/mfa';

/**
 * "Require an authenticator app for all members" (docs/totp.md): the owners'
 * rule, with who already has one. It applies at each member's next request;
 * nobody is signed out. Turning it on needs the owner's own session to have
 * used its authenticator app (the server says 409 `enrol_first`, or 403
 * `mfa_required` while the rule already holds), so an owner cannot lock
 * themselves out: the page then asks for the code, or sets an app up, and
 * tries again. Admins see the rule and the counts; only owners change it. The
 * page is absent while the server's `TOTP_ENABLED` switch is off.
 */
export default function WorkspaceTotpSection() {
    const { t } = useTranslation();
    const { toast } = useToast();
    const workspace = useAppSelector((state) => state.workspace);
    const { can } = useWorkspacePermissions();
    const canSee = can(WorkspacePermission.SECURITY_MANAGE);
    // every owner holds workspace.billing; the server decides on its own
    const isOwner = can(WorkspacePermission.WORKSPACE_BILLING);
    const { data: policy, isLoading } = useGetWorkspaceTotpPolicyQuery(workspace?.id as string, { skip: !workspace?.id || !canSee });
    const { data: mine } = useGetMfaStatusQuery();
    const [setPolicy, { isLoading: saving }] = useSetWorkspaceTotpPolicyMutation();
    const [logout] = useLogoutMutation();
    const [confirming, setConfirming] = useState(false);
    const [gate, setGate] = useState(false);
    const [error, setError] = useState('');

    if (!canSee) {
        return <p className="pb-10 text-sm text-black-600">{t('STAFF.MFA.POLICY.ONLY_ADMINS')}</p>;
    }
    if (isLoading) return <p className="pb-10 text-sm text-black-600">{t('STAFF.MFA.POLICY.LOADING')}</p>;
    if (!policy?.available) return null;

    const change = async (required: boolean) => {
        setError('');
        const answer = await setPolicy({ workspaceId: workspace.id, required });
        if ('data' in answer && answer.data) {
            setConfirming(false);
            toast({ description: t(required ? 'STAFF.MFA.POLICY.TURNED_ON' : 'STAFF.MFA.POLICY.TURNED_OFF') });
            return;
        }
        const refused = mfaFailureOf((answer as { error?: unknown }).error);
        if (refused.code === 'enrol_first' || refused.code === 'mfa_required') {
            // the owner's own session has not used its app yet
            setConfirming(false);
            setGate(true);
            return;
        }
        setError(mfaErrorText(t, refused));
    };

    const signInAgain = async () => {
        await logout();
        navigateTo(`/login?redirect_to=${encodeURIComponent(window.location.pathname)}`);
    };

    return (
        <section aria-labelledby="totp-policy-title" className="flex w-full max-w-[760px] flex-col gap-4 pb-10">
            <div className="flex flex-col gap-1">
                <h2 id="totp-policy-title" className="text-sm font-semibold text-black-900">
                    {t('STAFF.MFA.POLICY.TITLE')}
                </h2>
                <p className="max-w-[62ch] text-xs leading-relaxed text-black-600">{t('STAFF.MFA.POLICY.INTRO')}</p>
            </div>
            <div className="flex flex-col gap-3 rounded-md border border-black-300 bg-white px-4 py-4">
                <p data-testid="totp-policy-state" className="text-[13px] font-medium text-black-800">
                    {t(policy.required ? 'STAFF.MFA.POLICY.STATE_ON' : 'STAFF.MFA.POLICY.STATE_OFF')}
                </p>
                <p data-testid="totp-policy-counts" className="text-xs leading-relaxed text-black-700">
                    {t('STAFF.MFA.POLICY.COUNTS', { without: policy.membersWithoutFactor, members: policy.members })}
                </p>
                <div className="flex flex-wrap items-center gap-3">
                    {isOwner ? (
                        policy.required ? (
                            <Button type="button" variant="v2Button" size="sm" isLoading={saving} onClick={() => void change(false)}>
                                {t('STAFF.MFA.POLICY.STOP')}
                            </Button>
                        ) : (
                            <Button type="button" size="sm" onClick={() => setConfirming(true)}>
                                {t('STAFF.MFA.POLICY.REQUIRE')}
                            </Button>
                        )
                    ) : (
                        <p className="text-xs text-black-600">{t('STAFF.MFA.POLICY.ONLY_OWNERS')}</p>
                    )}
                </div>
                {error && (
                    <p role="alert" className="text-xs leading-relaxed font-medium text-[#B42318]">
                        {error}
                    </p>
                )}
            </div>

            {confirming && (
                <Dialog open onOpenChange={(open) => !open && setConfirming(false)}>
                    <DialogContent className="max-w-lg" title={t('STAFF.MFA.POLICY.CONFIRM_TITLE')}>
                        <div className="flex flex-col gap-4 pr-6">
                            <div aria-hidden="true" className="text-lg font-semibold text-black-900">
                                {t('STAFF.MFA.POLICY.CONFIRM_TITLE')}
                            </div>
                            <ul className="flex list-disc flex-col gap-2 pl-5 text-sm leading-relaxed text-black-800">
                                <li>{policy.membersWithoutFactor > 0 ? t('STAFF.MFA.POLICY.CONFIRM_WITHOUT', { without: policy.membersWithoutFactor, members: policy.members }) : t('STAFF.MFA.POLICY.CONFIRM_ALL')}</li>
                                <li>{t('STAFF.MFA.POLICY.CONFIRM_SIGNED_IN')}</li>
                            </ul>
                            {error && (
                                <p role="alert" className="text-xs font-medium text-[#B42318]">
                                    {error}
                                </p>
                            )}
                            <div className="flex justify-end gap-2">
                                <Button type="button" variant="v2Button" size="sm" onClick={() => setConfirming(false)}>
                                    {t('STAFF.MFA.POLICY.CANCEL')}
                                </Button>
                                <Button type="button" size="sm" isLoading={saving} onClick={() => void change(true)}>
                                    {t('STAFF.MFA.POLICY.CONFIRM')}
                                </Button>
                            </div>
                        </div>
                    </DialogContent>
                </Dialog>
            )}

            {gate && mine?.enabled && (
                <Dialog open onOpenChange={(open) => !open && setGate(false)}>
                    <DialogContent className="max-w-md" title={t('STAFF.MFA.POLICY.FIRST_TITLE')}>
                        <div className="flex flex-col gap-4 pr-6">
                            <MfaCodeForm
                                session
                                heading={t('STAFF.MFA.POLICY.FIRST_TITLE')}
                                intro={t('STAFF.MFA.POLICY.FIRST_INTRO')}
                                backLabel={t('STAFF.MFA.POLICY.CANCEL')}
                                onBack={() => setGate(false)}
                                onSignedIn={() => {
                                    setGate(false);
                                    void change(true);
                                }}
                            />
                        </div>
                    </DialogContent>
                </Dialog>
            )}
            {gate && !mine?.enabled && (
                <TotpEnrolDialog
                    onClose={() => setGate(false)}
                    onSignInAgain={signInAgain}
                    onEnrolled={() => {
                        void change(true);
                    }}
                />
            )}
        </section>
    );
}
