import { useState } from 'react';

import { useRouter } from 'next/router';

import { toast } from 'react-toastify';

import BetterInput from '@app/components/common/input';
import { useModal } from '@app/components/modal-views/context';
import SettingsCard from '@app/components/settings/card';
import Button from '@app/components/ui/button';
import { selectIsProPlan } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';
import { useInviteToWorkspaceMutation } from '@app/store/workspaces/members-n-invitations-api';

export default function InviteMemberModal() {
    const [trigger, { data, isLoading }] = useInviteToWorkspaceMutation();
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
                toast('Invitation Sent', { type: 'success' });
            } else if (response.error) {
                toast('Failed to send email.', { type: 'error' });
            }
            closeModal();
        } else {
            router.push(`/${workspace.workspaceName}/upgrade`);
        }
    };
    return (
        <>
            <SettingsCard>
                <div className="h4">Invite Collaborator</div>
                <div className="body4">A collaborator can import and manage forms in workspace.</div>
                <form onSubmit={handleSendInvitation} className="flex  flex-col justify-start">
                    <div className="body1">Enter Email</div>
                    <BetterInput
                        disabled={isLoading}
                        data-testid="otp-input"
                        spellCheck={false}
                        value={invitationMail}
                        type="email"
                        placeholder={'Enter Email'}
                        onChange={(event) => {
                            setInvitationMail(event.target.value);
                        }}
                    />
                    <div className="flex w-full justify-end">
                        <Button disabled={isLoading} isLoading={isLoading} size="small" type="submit">
                            Send Invitation
                        </Button>
                    </div>
                </form>
            </SettingsCard>
        </>
    );
}
