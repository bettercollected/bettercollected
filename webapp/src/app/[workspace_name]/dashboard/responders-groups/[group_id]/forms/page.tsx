'use client';

import React from 'react';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { useGetRespondersGroupQuery, useGetWorkspaceFormsQuery } from '@app/store/workspaces/api';
import GroupFormsTab from '@app/Components/group-preview/forms';
import Loader from '@app/Components/ui/loader';
import { useParams } from 'next/navigation';

export default function GroupFormsPage() {
    const workspace = useAppSelector(selectWorkspace);
    const params = useParams();
    const groupId = params?.group_id as string;

    const { data: groupData, isLoading: isGroupLoading } = useGetRespondersGroupQuery({
        workspaceId: workspace?.id,
        groupId: groupId
    }, { skip: !workspace?.id || !groupId });

    const { data: workspaceForms, isLoading: isFormsLoading } = useGetWorkspaceFormsQuery<any>({ workspace_id: workspace?.id }, { skip: !workspace?.id });

    if (isGroupLoading || isFormsLoading) return <Loader />;

    return <GroupFormsTab group={groupData} workspaceForms={workspaceForms?.items} />;
}
