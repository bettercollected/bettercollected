import React from 'react';

import { Typography } from '@mui/material';

import GroupCard from '@app/components/cards/group-card';
import { Plus } from '@app/components/icons/plus';
import UserMore from '@app/components/icons/user-more';
import { useModal } from '@app/components/modal-views/context';
import Button from '@app/components/ui/button/button';
import Loader from '@app/components/ui/loader';
import { ResponderGroupDto } from '@app/models/dtos/groups';
import { useAppSelector } from '@app/store/hooks';
import { useGetAllRespondersGroupQuery } from '@app/store/workspaces/api';

export default function WorkspaceGropus() {
    const { openModal } = useModal();
    const workspace = useAppSelector((state) => state.workspace);
    const { data, isLoading } = useGetAllRespondersGroupQuery(workspace.id);
    const emptyGroup = () => (
        <div className="my-[119px] flex flex-col items-center">
            <UserMore />
            <p className="body1">Create a group to :</p>
            <ul className="list-disc body4 text-black-700 flex flex-col gap-4 mt-4">
                <li>Limit access to form from your workspace</li>
                <li>Send forms to multiple people at the same time</li>
            </ul>
            <Button className="mt-6" size="small" onClick={() => openModal('CREATE_GROUP')}>
                Create New Group
            </Button>
        </div>
    );
    const group = () => (
        <div>
            <div className="flex justify-between">
                <p className="body1">Groups {data && ' (' + data.length + ')'} </p>
                <div onClick={() => openModal('CREATE_GROUP')} className="flex gap-2 p-2 group hover:bg-brand-500 hover:text-white rounded text-brand-500 items-center cursor-pointer">
                    <Plus className="h-4 w-4" />
                    <Typography className="!text-brand-500 group-hover:!text-white body6"> Create Group</Typography>
                </div>
            </div>
            <p className="mt-4 mb-8 body4 sm:max-w-[355px] text-black-700">Send forms to entire groups, streamlining the process and saving time.</p>
            <div className="grid sm:grid-cols-2  grid-flow-row gap-6">
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
    if (data && data?.length > 0) return group();
    return emptyGroup();
}
