'use client';

import WorkspaceResponses from '@app/components/workspace-responders/workspace-responders';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';

export default function AllRespondersPage() {
    const workspace = useAppSelector(selectWorkspace);
    return <WorkspaceResponses workspace={workspace} />;
}
