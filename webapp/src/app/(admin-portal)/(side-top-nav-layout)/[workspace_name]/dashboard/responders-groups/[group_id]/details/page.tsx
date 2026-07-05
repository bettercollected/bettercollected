'use client';

import GroupDetailsTab from '@app/components/group-preview/group-details';
import Loader from '@app/components/ui/loader';
import { useAppSelector } from '@app/store/hooks';
import { useGetRespondersGroupQuery } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';
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
