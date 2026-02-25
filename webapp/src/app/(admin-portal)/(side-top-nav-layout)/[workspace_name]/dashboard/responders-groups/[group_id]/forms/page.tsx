'use client';

import GroupFormsTab from '@app/components/group-preview/forms';
import Loader from '@app/components/ui/loader';
import { useAppSelector } from '@app/store/hooks';
import { useGetRespondersGroupQuery, useGetWorkspaceFormsQuery } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';
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
