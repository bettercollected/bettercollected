'use client';

import { useWorkspacePermissions } from '@app/lib/hooks/use-workspace-permissions';
import { WorkspacePermission } from '@app/models/enums/workspace-permission';

interface IWorkspaceAdminSelectorProps {
    children: React.ReactNode | React.ReactNode[];
}

/** Renders its children for the workspace owner only (workspace.billing:
 *  the plan and Stripe billing are the owner's). */
export default function WorkspaceAdminSelector({ children }: IWorkspaceAdminSelectorProps) {
    const { can } = useWorkspacePermissions();

    if (can(WorkspacePermission.WORKSPACE_BILLING)) return <>{children}</>;
    return null;
}
