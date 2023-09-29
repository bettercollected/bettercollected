import React from 'react';

import {useTranslation} from 'next-i18next';

import Plus from '@Components/Common/Icons/Plus';

import {useModal} from '@app/components/modal-views/context';
import {inviteCollaborator} from '@app/constants/locales/inviteCollaborator';
import {members} from '@app/constants/locales/members';
import {useAppSelector} from '@app/store/hooks';
import {useGetWorkspaceMembersQuery} from '@app/store/workspaces/members-n-invitations-api';

import MembersTable from '../settings/members-table';
import Loader from '../ui/loader';
import AppButton from "@Components/Common/Input/Button/AppButton";
import {ButtonVariant} from "@Components/Common/Input/Button/AppButtonProps";

export default function Collaborators() {
    const workspace = useAppSelector((state) => state.workspace);
    const {data, isLoading} = useGetWorkspaceMembersQuery({workspaceId: workspace.id});
    const {t} = useTranslation();
    const {openModal} = useModal();
    if (isLoading) {
        return (
            <div className=" w-full py-10 flex justify-center">
                <Loader/>
            </div>
        );
    }
    return (
        <div className="flex flex-col gap-4 ">
            <div className="flex justify-between flex-row">
                <p className="body1 ">
                    {t(members.collaborators.default)} ({data?.length})
                </p>
                <AppButton
                    variant={ButtonVariant.Ghost}
                    onClick={() => {
                        openModal('INVITE_MEMBER');
                    }}
                    icon={<Plus className="h-4 w-4"/>}
                >
                    {t(inviteCollaborator.default)}
                </AppButton>
            </div>


            <p className="body4 mb-6 md:max-w-[301px] text-black-700">{t(members.collaborators.description)}</p>
            <MembersTable data={data}/>
        </div>
    );
}
