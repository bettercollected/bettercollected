import React from 'react';
import { notFound } from 'next/navigation';
import { cookies } from 'next/headers';
import environments from '@app/configs/environments';
import ServerSideWorkspaceDispatcher from '@app/Components/HOCs/ServerSideWorkspaceDispatcher';
import { getWorkspaceByName } from '@app/app/\[workspace_name\]/dashboard/layout';
import FormDashboardClient from './FormDashboardClient';

async function getForm(workspaceId: string, formId: string) {
    const cookieStore = await cookies();
    const auth = (await cookieStore.get('Authorization'))?.value;
    const refresh = (await cookieStore.get('RefreshToken'))?.value;
    const cookieHeader = [
        auth ? `Authorization=${auth}` : '',
        refresh ? `RefreshToken=${refresh}` : ''
    ].filter(Boolean).join(';');

    try {
        const res = await fetch(`${environments.INTERNAL_DOCKER_API_ENDPOINT_HOST}/workspaces/${workspaceId}/forms/${formId}?published=true&draft=true`, {
            headers: {
                cookie: cookieHeader
            },
            cache: 'no-store',
        });
        if (!res.ok) return null;
        return res.json();
    } catch (e) {
        return null;
    }
}

export default async function FormDashboardPage({ params }: { params: Promise<{ workspace_name: string; form_id: string }> }) {
    const { workspace_name, form_id } = await params;
    const workspace = await getWorkspaceByName(workspace_name);
    if (!workspace) return notFound();

    const form = await getForm(workspace.id, form_id);
    if (!form) return notFound();

    return (
        <ServerSideWorkspaceDispatcher workspace={workspace}>
            <FormDashboardClient form={form} />
        </ServerSideWorkspaceDispatcher>
    );
}
