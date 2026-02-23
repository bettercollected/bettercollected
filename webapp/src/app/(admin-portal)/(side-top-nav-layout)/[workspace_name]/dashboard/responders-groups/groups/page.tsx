'use client';

import React from 'react';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';
import WorkspaceGroups from '@Components/workspace-responders/workspace-groups';

export default function GroupsPage() {
    const workspace = useAppSelector(selectWorkspace);
    return <WorkspaceGroups workspace={workspace} />;
}
