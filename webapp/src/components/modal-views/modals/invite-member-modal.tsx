import { useState } from 'react';

import { useTranslation } from 'next-i18next';
import { useRouter } from 'next/router';

import { toast } from 'react-toastify';

import BetterInput from '@app/components/Common/input';
import { Close } from '@app/components/icons/close';
import { useModal } from '@app/components/modal-views/context';
import SettingsCard from '@app/components/settings/card';
import Button from '@app/components/ui/button';
import { buttonConstant } from '@app/constants/locales/buttons';
import { localesGlobal } from '@app/constants/locales/global';
import { inviteCollaborator } from '@app/constants/locales/inviteCollaborator';
import { toastMessage } from '@app/constants/locales/toast-message';
import { selectIsProPlan } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';
import { useInviteToWorkspaceMutation } from '@app/store/workspaces/members-n-invitations-api';

export default function InviteMemberModal() {
    const [trigger, { data, isLoading }] = useInviteToWorkspaceMutation();
    const { t } = useTranslation();
    const [invitationMail, setInvitationMail] = useState('');
    const workspace = useAppSelector((state) => state.workspace);
    const router = useRouter();
    const isProPlan = useAppSelector(selectIsProPlan);
    const { closeModal } = useModal();
    const handleSendInvitation = async (e: any) => {
        e.preventDefault();
        if (!invitationMail) {
            return;
        }
        if (isProPlan) {
            const response: any = await trigger({
                workspaceId: workspace.id,
                body: {
                    role: 'COLLABORATOR',
                    email: invitationMail
                }
            });

            if (response.data) {
                setInvitationMail('');
                toast(t(toastMessage.invitationSent).toString(), { type: 'success' });
            } else if (response.error) {
                toast(t(toastMessage.failedToSentEmail).toString(), { type: 'error' });
            }
            closeModal();
        } else {
            router.push(`/${workspace.workspaceName}/upgrade`);
        }
    };
    return (
        <>
            <SettingsCard className="!space-y-0 relative">
                <Close onClick={closeModal} className="absolute top-2 right-2 cursor-pointer p-2 h-8 w-8" />
                <div className="sh1 !leading-none">{t(inviteCollaborator.default)}</div>
                <div className="body4 pt-6 !leading-none ">{t(inviteCollaborator.description)}</div>
                <form onSubmit={handleSendInvitation} className="flex pt-8  flex-col justify-start">
                    <div className="body1 mb-3 !leading-none">{t(localesGlobal.enterEmail)}</div>
                    <BetterInput
                        disabled={isLoading}
                        data-testid="otp-input"
                        spellCheck={false}
                        value={invitationMail}
                        type="email"
                        className="!mb-0"
                        placeholder={t(localesGlobal.enterEmail)}
                        onChange={(event) => {
                            setInvitationMail(event.target.value);
                        }}
                    />
                    <div className="flex w-full mt-8 justify-end">
                        <Button disabled={isLoading} isLoading={isLoading} size="small" type="submit">
                            {t(buttonConstant.sendInvitation)}
                        </Button>
                    </div>
                </form>
            </SettingsCard>
        </>
    );
}
