import React from 'react';

import { useTranslation } from 'next-i18next';

import { Typography } from '@mui/material';

import GroupCard from '@app/components/cards/group-card';
import EmptyGroup from '@app/components/dashboard/empty-group';
import { Plus } from '@app/components/icons/plus';
import { useModal } from '@app/components/modal-views/context';
import Loader from '@app/components/ui/loader';
import { groupConstant } from '@app/constants/locales/group';
import { ResponderGroupDto } from '@app/models/dtos/groups';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { selectIsAdmin } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';
import { useGetAllRespondersGroupQuery } from '@app/store/workspaces/api';

export default function WorkspaceGropus({ workspace }: { workspace: WorkspaceDto }) {
    const { openModal } = useModal();
    const { t } = useTranslation();
    const isAdmin = useAppSelector(selectIsAdmin);
    const { data, isLoading } = useGetAllRespondersGroupQuery(workspace.id);
    const Group = () => (
        <div>
            <div className="flex justify-between">
                <p className="body1">
                    {t(groupConstant.groups)} {data && ' (' + data.length + ')'}{' '}
                </p>
                {isAdmin && (
                    <div onClick={() => openModal('CREATE_GROUP')} className="flex gap-2 p-2  text-brand-500 items-center cursor-pointer">
                        <Plus className="h-4 w-4" />
                        <Typography className="!text-brand-500  body6"> {t(groupConstant.createGroup)}</Typography>
                    </div>
                )}
            </div>
            <p className="mt-4 mb-8 body4 sm:max-w-[355px] text-black-700">{t(groupConstant.description)}</p>
            <div className="grid sm:grid-cols-2 2xl:grid-cols-3  grid-flow-row gap-6">
                {data &&
                    data?.map((group: ResponderGroupDto) => {
                        return <GroupCard key={group.id} responderGroup={group} />;
                    })}
            </div>
        </div>
    );
    if (isLoading)
        return (
            <div className=" w-full py-10 flex justify-center">
                <Loader />
            </div>
        );
    if (data && data?.length > 0) return Group();
    return <EmptyGroup />;
}
