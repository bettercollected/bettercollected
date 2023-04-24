import { useState } from 'react';

import { useRouter } from 'next/router';

import { toast } from 'react-toastify';

import BetterInput from '@app/components/common/input';
import ManageWorkspaceLayout from '@app/components/layout/manage-workspace';
import SettingsCard from '@app/components/settings/card';
import InvitationsTable from '@app/components/settings/invitations-table';
import MembersTable from '@app/components/settings/members-table';
import Button from '@app/components/ui/button';
import { selectIsProPlan } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';
import { useInviteToWorkspaceMutation } from '@app/store/workspaces/members-n-invitations-api';

export default function ManageMembers() {
    const [trigger, { data, isLoading }] = useInviteToWorkspaceMutation();
    const [invitationMail, setInvitationMail] = useState('');
    const workspace = useAppSelector((state) => state.workspace);
    const router = useRouter();
    const isProPlan = useAppSelector(selectIsProPlan);
    const handleSendInvitation = async (e: any) => {
        e.preventDefault();

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
                toast('Failed to send email.', { type: 'success' });
            }
        } else {
            router.push(`/${workspace.workspaceName}/upgrade`);
        }
    };

    return (
        <ManageWorkspaceLayout>
            <SettingsCard>
                <div className="body1">Invite Collaborator</div>
                <form onSubmit={handleSendInvitation} className="flex space-x-6 justify-start">
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
                    <Button disabled={isLoading} isLoading={isLoading} size="medium" type="submit">
                        Send Invitation
                    </Button>
                </form>
            </SettingsCard>
            <SettingsCard>
                <div className="body1">Members</div>
                <MembersTable />
            </SettingsCard>
            {isProPlan && (
                <SettingsCard>
                    <div className="body1">Invitations</div>
                    <InvitationsTable />
                </SettingsCard>
            )}
        </ManageWorkspaceLayout>
    );
}

export { getServerSidePropsForWorkspaceAdmin as getServerSideProps } from '@app/lib/serverSideProps';
