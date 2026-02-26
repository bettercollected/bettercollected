'use client';

import WorkspaceResponsesTabContent from '@app/components/dashboard/workspace-responses-tab-content';
import { selectAuth } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';

export default function PortalDeletionRequestsPage() {
    const workspace = useAppSelector(selectWorkspace);
    const auth = useAppSelector(selectAuth);

    if (!auth.id) return null;

    return <WorkspaceResponsesTabContent workspace={workspace} deletionRequests />;
}
