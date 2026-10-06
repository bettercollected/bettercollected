'use client';

import { useWorkspacePermissions } from '@app/lib/hooks/use-workspace-permissions';
import { WorkspacePermission } from '@app/models/enums/workspace-permission';

interface IWorkspaceAdminSelectorProps {
    children: React.ReactNode | React.ReactNode[];
}

/** Renders its children for the workspace's owners only (workspace.billing,
 *  which every owner holds; the plan itself is the billing owner's). */
export default function WorkspaceAdminSelector({ children }: IWorkspaceAdminSelectorProps) {
    const { can } = useWorkspacePermissions();

    if (can(WorkspacePermission.WORKSPACE_BILLING)) return <>{children}</>;
    return null;
}
