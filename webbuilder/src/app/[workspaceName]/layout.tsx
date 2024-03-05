import React, { Suspense } from 'react';

import { WorkspaceDispatcher } from './_dispatcher/WorkspaceDispatcher';

export default function WorkspaceLayout({
    children,
    params
}: Readonly<{ children: React.ReactNode; params: { workspaceName: string } }>) {
    return (
        <main className="h-full">
            <WorkspaceWrapper workspaceName={params.workspaceName}>
                {children}
            </WorkspaceWrapper>
        </main>
    );
}

const getWorkspaceByName = async (workspaceName: string) => {
    const workspaceResponse = await fetch(
        process.env.API_ENDPOINT_HOST + '/workspaces?workspace_name=' + workspaceName
    );

    return await workspaceResponse.json();
};

async function WorkspaceWrapper({
    workspaceName,
    children
}: {
    workspaceName: string;
    children: React.ReactNode;
}) {
    // const workspace = await getWorkspaceByName(workspaceName);
    const workspace = '';

    return (
        <>
            <Suspense fallback={<>Loading</>}>
                <WorkspaceDispatcher workspace={workspace}>
                    {children}
                </WorkspaceDispatcher>
            </Suspense>
        </>
    );
}
