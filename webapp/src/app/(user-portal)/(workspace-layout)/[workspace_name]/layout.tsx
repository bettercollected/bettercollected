import { getWorkspaceByName } from '@app/app/(admin-portal)/(side-top-nav-layout)/[workspace_name]/dashboard/layout';
import { WorkspaceDispatcher } from '@app/app/_dispatcher/workspace-dispatcher';
import ResponderPortalLayoutClient from '@Components/responder-portal/responder-portal-layout-client';
import React from 'react';

export default async function ResponderPortalLayout({
    children, params
}: {
    children: React.ReactNode,
    params: Promise<{ workspace_name: string }>
}) {
    const { workspace_name } = await params;
    const workspace = await getWorkspaceByName(workspace_name);
    return (
        <WorkspaceDispatcher workspace={workspace}>
            <ResponderPortalLayoutClient hasCustomDomain={false}>
                {children}
            </ResponderPortalLayoutClient>
        </WorkspaceDispatcher>
    );
}
