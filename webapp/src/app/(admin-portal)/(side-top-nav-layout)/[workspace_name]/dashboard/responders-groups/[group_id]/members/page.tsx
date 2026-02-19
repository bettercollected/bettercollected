'use client';

import React from 'react';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { useGetRespondersGroupQuery } from '@app/store/workspaces/api';
import GroupMembersTab from '@app/Components/group-preview/member';
import Loader from '@app/Components/ui/loader';
import { useParams } from 'next/navigation';

export default function GroupMembersPage() {
    const workspace = useAppSelector(selectWorkspace);
    const params = useParams();
    const groupId = params?.group_id as string;

    const { data: groupData, isLoading } = useGetRespondersGroupQuery({
        workspaceId: workspace?.id,
        groupId: groupId
    }, { skip: !workspace?.id || !groupId });

    if (isLoading) return <Loader />;

    return <GroupMembersTab group={groupData} workspace={workspace} />;
}
