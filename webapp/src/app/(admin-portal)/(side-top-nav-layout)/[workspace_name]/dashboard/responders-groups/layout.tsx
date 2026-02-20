import { WorkspaceDispatcher } from '@app/app/_dispatcher/WorkspaceDispatcher';
import { notFound } from 'next/navigation';
import React from 'react';
import { getWorkspaceByName } from '../layout';
import RespondersGroupsLayoutClient from './_components/RespondersGroupsLayoutClient';

export default async function RespondersGroupsLayout({
    children,
    params
}: {
    children: React.ReactNode;
    params: Promise<{ workspace_name: string }>;
}) {
    const { workspace_name } = await params;
    const workspace = await getWorkspaceByName(workspace_name);

    if (!workspace) return notFound();

    return (
        <WorkspaceDispatcher workspace={workspace}>
            <RespondersGroupsLayoutClient workspaceName={workspace_name}>
                {children}
            </RespondersGroupsLayoutClient>
        </WorkspaceDispatcher>
    );
}
