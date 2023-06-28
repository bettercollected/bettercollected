import React from 'react';

import { useTranslation } from 'next-i18next';

import Plus from '@Components/Common/Icons/Plus';
import { Typography } from '@mui/material';

import { useModal } from '@app/components/modal-views/context';
import { inviteCollaborator } from '@app/constants/locales/inviteCollaborator';
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
        <div className="relative">
            <div
                onClick={() => {
                    openModal('INVITE_MEMBER');
                }}
                className="flex gap-2 top-5 right-0 p-2 absolute text-brand-500 items-center cursor-pointer"
            >
                <Plus className="h-4 w-4" />
                <Typography className="!text-brand-500  body6"> {t(inviteCollaborator.default)}</Typography>
            </div>
            <p className="body1 ">
                {t(members.collaborators.default)} ({data?.length})
            </p>
            <p className="body4 mt-4 mb-6 md:max-w-[301px] text-black-700">{t(members.collaborators.description)}</p>
            <MembersTable data={data} />
        </div>
    );
}
