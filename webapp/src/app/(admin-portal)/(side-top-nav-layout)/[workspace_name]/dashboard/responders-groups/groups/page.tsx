'use client';

import WorkspaceGroups from '@app/components/workspace-responders/workspace-groups';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';

export default function GroupsPage() {
    const workspace = useAppSelector(selectWorkspace);
    return <WorkspaceGroups workspace={workspace} />;
}
