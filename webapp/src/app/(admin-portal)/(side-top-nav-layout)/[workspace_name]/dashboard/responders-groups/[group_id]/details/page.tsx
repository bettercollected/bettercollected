'use client';

import React from 'react';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { useGetRespondersGroupQuery } from '@app/store/workspaces/api';
import GroupDetailsTab from '@app/Components/group-preview/group-details';
import Loader from '@app/Components/ui/loader';
import { useParams } from 'next/navigation';

export default function GroupDetailsPage() {
    const workspace = useAppSelector(selectWorkspace);
    const params = useParams();
    const groupId = params?.group_id as string;

    const { data: groupData, isLoading } = useGetRespondersGroupQuery({
        workspaceId: workspace?.id,
        groupId: groupId
    }, { skip: !workspace?.id || !groupId });

    if (isLoading) return <Loader />;

    return <GroupDetailsTab group={groupData} />;
}
