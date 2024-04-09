import React, { Suspense } from 'react';

import { notFound } from 'next/navigation';

import { setWorkspace } from '@app/store/redux/workspace';
import { store } from '@app/store/store';
import FullScreenLoader from '@app/views/atoms/Loaders/FullScreenLoader';

import { WorkspaceDispatcher } from './_dispatcher/WorkspaceDispatcher';

export default function WorkspaceLayout({
    children,
    params
}: Readonly<{ children: React.ReactNode; params: { workspaceName: string } }>) {
    return (
        <WorkspaceWrapper workspaceName={params.workspaceName}>
            {children}
        </WorkspaceWrapper>
    );
}

const getWorkspaceByName = async (workspaceName: string) => {
    const workspaceResponse = await fetch(
        process.env.API_ENDPOINT_HOST + '/workspaces?workspace_name=' + workspaceName
    );

    const workspace = await workspaceResponse.json();
    store.dispatch(setWorkspace(workspace));
    return workspace;
};

async function WorkspaceWrapper({
    workspaceName,
    children
}: {
    workspaceName: string;
    children: React.ReactNode;
}) {
    const workspace = await getWorkspaceByName(workspaceName);

    if (!workspace.id) {
        return notFound();
    }

    return (
        <Suspense fallback={<FullScreenLoader />}>
            <WorkspaceDispatcher workspace={workspace}>{children}</WorkspaceDispatcher>
        </Suspense>
    );
}
