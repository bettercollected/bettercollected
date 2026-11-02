'use client';

import React, { useState } from 'react';

import { useTranslation } from 'react-i18next';

import OwnFactorGate from '@app/components/mfa/own-factor-gate';
import { WorkspaceMembersDto } from '@app/models/dtos/workspace-member-dto';
import { Button } from '@app/shadcn/components/ui/button';
import { Dialog, DialogContent } from '@app/shadcn/components/ui/dialog';
import { useToast } from '@app/shadcn/components/ui/use-toast';
import { useResetMemberTotpMutation } from '@app/store/workspaces/members-n-invitations-api';
import { mfaFailureOf } from '@app/utils/mfa';

/** What the person who asked to reset a member's second factor is told when the server refuses. */
export function resetFailureKey(failure: { status?: number; code?: string }): string {
    if (failure.code === 'reset_admin_not_allowed') return 'STAFF.MFA.RESET.ADMIN_NOT_ALLOWED';
    if (failure.code === 'reset_not_allowed') return 'STAFF.MFA.RESET.NOT_ALLOWED';
    if (failure.code === 'reset_self') return 'STAFF.MFA.RESET.SELF';
    if (failure.status === 404) return 'STAFF.MFA.RESET.GONE';
    return 'STAFF.MFA.RESET.FAILED';
}

/**
 * An owner removes a member's authenticator app (the member lost the phone and
 * the recovery codes). The consequences are listed before it is done: their
 * sessions end, they are emailed, they can set up again. Never shows a secret
 * or a code of the member.
 */
export default function ResetTotpDialog({ workspaceId, member, onClose }: { workspaceId: string; member: WorkspaceMembersDto; onClose: () => void }) {
    const { t } = useTranslation();
    const { toast } = useToast();
    const [reset, { isLoading }] = useResetMemberTotpMutation();
    // 409 `enrol_first`: the owner's own session must have used its own app before removing someone else's
    const [gate, setGate] = useState(false);
    const name = [member.firstName, member.lastName].filter(Boolean).join(' ') || member.email;

    const submit = async () => {
        const answer = await reset({ workspaceId, userId: member.id });
        if ('error' in answer && answer.error) {
            const failure = mfaFailureOf(answer.error);
            if (failure.code === 'enrol_first') {
                setGate(true);
                return;
            }
            toast({ description: t(resetFailureKey(failure)), variant: 'destructive' });
            return;
        }
        toast({ description: t('STAFF.MFA.RESET.DONE') });
        onClose();
    };

    if (gate) {
        return (
            <OwnFactorGate
                onCancel={() => setGate(false)}
                onDone={() => {
                    setGate(false);
                    void submit();
                }}
            />
        );
    }

    return (
        <Dialog open onOpenChange={(open) => !open && onClose()}>
            <DialogContent className="max-w-lg" title={t('STAFF.MFA.RESET.TITLE')}>
                <div className="flex flex-col gap-4 pr-6">
                    <div aria-hidden="true" className="text-lg font-semibold text-black-900">
                        {t('STAFF.MFA.RESET.TITLE')}
                    </div>
                    <p className="text-sm leading-relaxed text-black-800">{t('STAFF.MFA.RESET.INTRO', { name })}</p>
                    <ul className="flex list-disc flex-col gap-2 pl-5 text-sm leading-relaxed text-black-800">
                        <li>{t('STAFF.MFA.RESET.EFFECT_SESSIONS')}</li>
                        <li>{t('STAFF.MFA.RESET.EFFECT_AGAIN')}</li>
                    </ul>
                    <div className="flex justify-end gap-2">
                        <Button type="button" variant="v2Button" size="sm" onClick={onClose}>
                            {t('STAFF.MFA.CANCEL')}
                        </Button>
                        <Button type="button" variant="danger" size="sm" isLoading={isLoading} onClick={submit}>
                            {t('STAFF.MFA.RESET.CONFIRM')}
                        </Button>
                    </div>
                </div>
            </DialogContent>
        </Dialog>
    );
}
