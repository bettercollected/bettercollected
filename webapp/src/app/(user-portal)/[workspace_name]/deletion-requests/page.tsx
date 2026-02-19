'use client';

import React from 'react';
import WorkspaceResponsesTabContent from '@Components/dashboard/workspace-responses-tab-content';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { selectAuth } from '@app/store/auth/slice';

export default function PortalDeletionRequestsPage() {
    const workspace = useAppSelector(selectWorkspace);
    const auth = useAppSelector(selectAuth);

    if (!auth.id) return null;

    return <WorkspaceResponsesTabContent workspace={workspace} deletionRequests />;
}
