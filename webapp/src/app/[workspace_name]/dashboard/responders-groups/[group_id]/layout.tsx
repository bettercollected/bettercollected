import React from 'react';
import { notFound } from 'next/navigation';
import ServerSideWorkspaceDispatcher from '@app/Components/HOCs/ServerSideWorkspaceDispatcher';
import { getWorkspaceByName } from '../../layout';
import GroupPreviewLayoutClient from './_components/GroupPreviewLayoutClient';

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
        <ServerSideWorkspaceDispatcher workspace={workspace}>
            <GroupPreviewLayoutClient workspaceName={workspace_name} groupId={group_id}>
                {children}
            </GroupPreviewLayoutClient>
        </ServerSideWorkspaceDispatcher>
    );
}
