import React, { Suspense } from 'react';

import { notFound } from 'next/navigation';

import FullScreenLoader from '@app/views/atoms/Loaders/FullScreenLoader';

import { WorkspaceDispatcher } from './_dispatcher/WorkspaceDispatcher';
import environments from '@app/configs/environments';

export async function generateMetadata({ params }: { params: { workspace_name: string } }) {
    return {
        title: 'Create | ' + params.workspace_name
    };
}

export default function WorkspaceLayout({ children, params }: Readonly<{ children: React.ReactNode; params: { workspace_name: string } }>) {
    return <WorkspaceWrapper workspaceName={params.workspace_name}>{children}</WorkspaceWrapper>;
}

const getWorkspaceByName = async (workspaceName: string) => {
    const workspaceResponse = await fetch(environments.INTERNAL_DOCKER_API_ENDPOINT_HOST + '/workspaces?workspace_name=' + workspaceName);

    const workspace = await workspaceResponse.json();

    return workspace;
};

async function WorkspaceWrapper({ workspaceName, children }: { workspaceName: string; children: React.ReactNode }) {
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
