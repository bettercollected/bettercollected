import React from 'react';
import { notFound } from 'next/navigation';
import ServerSideWorkspaceDispatcher from '@app/Components/HOCs/ServerSideWorkspaceDispatcher';
import { getWorkspaceByName } from '../../layout';
import GroupPreviewClient from './GroupPreviewClient';

export default async function GroupPreviewPage({ params }: { params: Promise<{ workspace_name: string, group_id: string }> }) {
    const { workspace_name, group_id } = await params;
    const workspace = await getWorkspaceByName(workspace_name);

    if (!workspace) return notFound();

    return (
        <ServerSideWorkspaceDispatcher workspace={workspace}>
            <GroupPreviewClient groupId={group_id} />
        </ServerSideWorkspaceDispatcher>
    );
}
