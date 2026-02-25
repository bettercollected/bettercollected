'use client';

import WorkspaceFormsTabContent from '@app/components/dashboard/workspace-forms-tab-content';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';

export default function PortalFormsPage() {
    const workspace = useAppSelector(selectWorkspace);
    return <WorkspaceFormsTabContent isFormCreator={false} workspace={workspace} />;
}
