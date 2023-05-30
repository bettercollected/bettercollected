import React from 'react';

import UserMore from '@app/components/icons/user-more';
import Loader from '@app/components/ui/loader';
import { useAppSelector } from '@app/store/hooks';
import { useGetAllRespondersGroupQuery } from '@app/store/workspaces/api';

import { useModal } from '../modal-views/context';
import Button from '../ui/button/button';

export default function WorkspaceGropus() {
    const { openModal } = useModal();
    const workspace = useAppSelector((state) => state.workspace);
    const { data, isLoading } = useGetAllRespondersGroupQuery(workspace.id);
    console.log(data);
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
        <div className="mt-[42px]">
            <div className="flex justify-between">
                <p className="body1">Groups {data && ' (' + data.length + ')'} </p>
                <Button size="medium" className="!bg-white">
                    Create Group
                </Button>
            </div>
            <p className="mt-4 mb-8 body4 text-black-700">Send forms to entire groups, streamlining the process and saving time.</p>
        </div>
    );

    if (isLoading)
        return (
            <div className=" w-full py-10 flex justify-center">
                <Loader />
            </div>
        );
    if (data && data.length > 0) return group();
    return emptyGroup();
}
