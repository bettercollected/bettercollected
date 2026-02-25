'use client';

import WorkspaceResponsesTabContent from '@app/components/dashboard/workspace-responses-tab-content';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';

export default function CustomSubmissionsPage() {
    const workspace = useAppSelector(selectWorkspace);
    return <WorkspaceResponsesTabContent workspace={workspace} />;
}
