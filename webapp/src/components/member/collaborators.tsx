
'use client';

import { useTranslation } from 'react-i18next';

import { Button } from '@app/shadcn/components/ui/button';
import { Plus } from 'lucide-react';

import { useModal } from '@app/components/modal-views/context';
import { inviteCollaborator } from '@app/constants/locales/invite-collaborators';
import { members } from '@app/constants/locales/members';
import { useAppSelector } from '@app/store/hooks';
import { useGetWorkspaceMembersQuery } from '@app/store/workspaces/members-n-invitations-api';

import MembersTable from '../settings/members-table';
import Loader from '../ui/loader';


export default function Collaborators() {
    const workspace = useAppSelector((state) => state.workspace);
    const { data, isLoading } = useGetWorkspaceMembersQuery({ workspaceId: workspace.id });
    const { t } = useTranslation();
    const { openModal } = useModal();
    if (isLoading) {
        return (
            <div className=" w-full py-10 flex justify-center">
                <Loader />
            </div>
        );
    }
    return (
        <div className="flex flex-col gap-4 ">
            <div className="flex justify-between flex-row">
                <p className="body1 ">
                    {t(members.collaborators.default)} ({data?.length})
                </p>
                <Button
                    variant="ghost"
                    onClick={() => {
                        openModal('INVITE_MEMBER');
                    }}
                    icon={<Plus className="h-4 w-4" />}
                >
                    {t(inviteCollaborator.default)}
                </Button>
            </div>

            <p className="body4 mb-6 md:max-w-[301px] text-black-700">{t(members.collaborators.description)}</p>
            <MembersTable data={data} />
        </div>
    );
}