'use client';

import React from 'react';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';
import WorkspaceResponses from '@Components/workspace-responders/workspace-responders';

export default function AllRespondersPage() {
    const workspace = useAppSelector(selectWorkspace);
    return <WorkspaceResponses workspace={workspace} />;
}
