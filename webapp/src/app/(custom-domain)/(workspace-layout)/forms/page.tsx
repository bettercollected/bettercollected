'use client';

import WorkspaceFormsTabContent from '@app/components/dashboard/workspace-forms-tab-content';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';

export default function CustomFormsPage() {
    const workspace = useAppSelector(selectWorkspace); // This relies on Redux state being populated.
    return <WorkspaceFormsTabContent isFormCreator={false} workspace={workspace} />;
}
