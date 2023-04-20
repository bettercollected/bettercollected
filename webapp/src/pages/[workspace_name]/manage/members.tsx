import { useState } from 'react';

import { toast } from 'react-toastify';

import ManageWorkspaceLayout from '@app/components/layout/manage-workspace';
import SettingsCard from '@app/components/settings/card';
import InvitationsTable from '@app/components/settings/invitations-table';
import MembersTable from '@app/components/settings/members-table';
import Button from '@app/components/ui/button';
import { useAppSelector } from '@app/store/hooks';
import { useInviteToWorkspaceMutation } from '@app/store/workspaces/members-n-invitations-api';

export default function ManageMembers() {
    const [trigger, { data, isLoading }] = useInviteToWorkspaceMutation();
    const [invitationMail, setInvitationMail] = useState('');
    const workspace = useAppSelector((state) => state.workspace);
    const handleSendInvitation = async (e: any) => {
        e.preventDefault();
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
    };

    return (
        <ManageWorkspaceLayout>
            <SettingsCard className="mt-10">
                <div className="body1">Invite Collaborator</div>
                <form onSubmit={handleSendInvitation} className="flex space-x-6 justify-start">
                    <input
                        disabled={isLoading}
                        data-testid="otp-input"
                        spellCheck={false}
                        value={invitationMail}
                        className={`border-solid flex-1 placeholder:font-normal placeholder:text-sm placeholder:tracking-normal mb-4 w-60 !rounded-[1px] !h-[50px] text-gray-900 p-2.5`}
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
            <SettingsCard className="mt-10">
                <div className="body1">Members</div>
                <MembersTable />
            </SettingsCard>
            <SettingsCard className="mt-10">
                <div className="body1">Invitations</div>
                <InvitationsTable />
            </SettingsCard>
        </ManageWorkspaceLayout>
    );
}

export { getAuthUserPropsWithWorkspace as getServerSideProps } from '@app/lib/serverSideProps';
