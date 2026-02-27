import { WorkspaceDispatcher } from '@app/app/_dispatcher/workspace-dispatcher';
import { getGroupById, getWorkspaceByName } from '@app/lib/server/api';
import { Metadata } from 'next';
import { notFound } from 'next/navigation';
import React from 'react';
import GroupPreviewLayoutClient from './_components/group-preview-layout-client';

export async function generateMetadata({ params }: { params: Promise<{ workspace_name: string; group_id: string }> }): Promise<Metadata> {
    const { workspace_name, group_id } = await params;
    const workspace = await getWorkspaceByName(workspace_name);

    if (!workspace) {
        return {
            title: 'Workspace Not Found'
        };
    }

    const group = await getGroupById(workspace.id, group_id);
    return {
        title: group?.name || 'Group',
        description: group?.description || 'Group Details'
    };
}

export default async function GroupPreviewLayout({
    children,
    params
}: {
    children: React.ReactNode;
    params: Promise<{ workspace_name: string; group_id: string }>;
}) {
    const { workspace_name, group_id } = await params;
    const workspace = await getWorkspaceByName(workspace_name);

    if (!workspace) return notFound();

    return (
        <WorkspaceDispatcher workspace={workspace}>
            <GroupPreviewLayoutClient workspaceName={workspace_name} groupId={group_id}>
                {children}
            </GroupPreviewLayoutClient>
        </WorkspaceDispatcher>
    );
}
