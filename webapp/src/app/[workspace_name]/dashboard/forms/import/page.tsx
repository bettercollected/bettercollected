import React from 'react';
import { notFound } from 'next/navigation';
import ServerSideWorkspaceDispatcher from '@app/Components/HOCs/ServerSideWorkspaceDispatcher';
import { getWorkspaceByName } from '../../layout';
import ImportFormClient from './ImportFormClient';

export default async function ImportFormPage({ params }: { params: { workspace_name: string } }) {
    const { workspace_name } = await params;
    const workspace = await getWorkspaceByName(workspace_name);

    if (!workspace) return notFound();

    return (
        <ServerSideWorkspaceDispatcher workspace={workspace}>
            <ImportFormClient />
        </ServerSideWorkspaceDispatcher>
    );
}

export async function generateMetadata({ params }: { params: { workspace_name: string } }) {
    const { workspace_name } = await params;
    return {
        title: 'Import Form | ' + workspace_name
    };
}
