import { useState } from 'react';

import { useTranslation } from 'next-i18next';

import { Button } from '@app/shadcn/components/ui/button';
import { useToast } from '@app/shadcn/components/ui/use-toast';

import { Close } from '@app/components/icons/close';
import { useModal } from '@app/components/modal-views/context';
import SettingsCard from '@app/components/settings/card';
import { buttonConstant } from '@app/constants/locales/button';
import { localesCommon } from '@app/constants/locales/common';
import { inviteCollaborator } from '@app/constants/locales/invite-collaborators';
import { toastMessage } from '@app/constants/locales/toast-message';
import { AppInput } from '@app/shadcn/components/ui/input';
import { useAppSelector } from '@app/store/hooks';
import { useGetWorkspaceMembersQuery, useInviteToWorkspaceMutation } from '@app/store/workspaces/members-n-invitations-api';

export default function InviteMemberModal() {
    const { toast } = useToast();
    const [trigger, { data, isLoading }] = useInviteToWorkspaceMutation();
    const workspace = useAppSelector((state) => state.workspace);

    const { t } = useTranslation();
    const [invitationMail, setInvitationMail] = useState('');
    const workspaceMember = useGetWorkspaceMembersQuery({ workspaceId: workspace.id });

    const { closeModal } = useModal();
    const isMemberExist = () => {
        if (workspaceMember.data && workspaceMember.data?.filter((member) => member.email === invitationMail).length > 0) {
            return true;
        }
        return false;
    };
    const handleSendInvitation = async (e: any) => {
        e.preventDefault();
        if (!invitationMail) {
            return;
        }

        if (isMemberExist()) {
            toast({ description: t(toastMessage.emailAlreadyExist).toString(), variant: 'destructive' });
        } else {
            const response: any = await trigger({
                workspaceId: workspace.id,
                body: {
                    role: 'COLLABORATOR',
                    email: invitationMail
                }
            });

            if (response.data) {
                setInvitationMail('');
                toast({ description: t(toastMessage.invitationSent).toString() });
            } else if (response.error) {
                toast({ description: t(toastMessage.failedToSentEmail).toString(), variant: 'destructive' });
            }
        }

        closeModal();
    };
    return (
        <SettingsCard className="relative !space-y-0 px-10 py-6 pb-10">
            <Close onClick={closeModal} className="absolute right-2 top-2 h-8 w-8 cursor-pointer p-2" />
            <div className="text-black-900 text-lg font-semibold leading-snug">{t(inviteCollaborator.default)}</div>
            <div className="text-black-600 pt-3 text-sm leading-relaxed">{t(inviteCollaborator.description)}</div>
            <form onSubmit={handleSendInvitation} className="flex flex-col  justify-start pt-8">
                <div className="text-black-700 mb-2 text-sm font-medium">{t(localesCommon.enterEmail)}</div>
                <AppInput
                    disabled={isLoading}
                    data-testid="otp-input"
                    spellCheck={false}
                    value={invitationMail}
                    type="email"
                    placeholder={t(localesCommon.enterEmail)}
                    onChange={(event) => {
                        setInvitationMail(event.target.value);
                    }}
                />
                <div className="mt-4 flex w-full flex-col justify-end">
                    <Button size="medium" disabled={isLoading} isLoading={isLoading} type="submit">
                        {t(buttonConstant.sendInvitation)}
                    </Button>
                </div>
            </form>
        </SettingsCard>
    );
}
