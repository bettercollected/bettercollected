import { WorkspaceDispatcher } from '@app/app/_dispatcher/workspace-dispatcher';
import environments from '@app/configs/environments';
import { getWorkspaceByName } from '@app/lib/server/api';
import { headers } from 'next/headers';
import { notFound } from 'next/navigation';
import React from 'react';

export default async function ClientDomainLayout({ children, params }: { children: React.ReactNode, params: Promise<{ workspace_name: string }> }) {
    const headerList = await headers();
    const host = headerList.get('x-forwarded-host') || headerList.get('host') || '';

    const hasClientDomain = host === environments.FORM_DOMAIN;

    if (!hasClientDomain) {
        notFound();
    }

    const { workspace_name } = await params;

    const workspace = await getWorkspaceByName(workspace_name);

    if (!workspace?.id) {
        notFound();
    }

    return (
        <WorkspaceDispatcher workspace={workspace}>
            {children}
        </WorkspaceDispatcher>
    );
}
