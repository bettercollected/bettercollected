import { WorkspaceDispatcher } from '@app/app/_dispatcher/workspace-dispatcher';
import environments from '@app/configs/environments';
import { getWorkspaceByName } from '@app/lib/server/api';
import ResponderPortalLayoutClient from '@Components/responder-portal/responder-portal-layout-client';
import { headers } from 'next/headers';
import { notFound } from 'next/navigation';
import React from 'react';

export default async function ResponderPortalLayout({
    children, params
}: {
    children: React.ReactNode,
    params: Promise<{ workspace_name: string }>
}) {
    const headerList = await headers();
    const host = headerList.get('x-forwarded-host') || headerList.get('host') || '';

    const hasClientDomain = host === environments.FORM_DOMAIN;

    if (!hasClientDomain) {
        notFound();
    }
    const { workspace_name } = await params;
    const workspace = await getWorkspaceByName(workspace_name);
    return (
        <WorkspaceDispatcher workspace={workspace}>
            <ResponderPortalLayoutClient hasCustomDomain={false}>
                {children}
            </ResponderPortalLayoutClient>
        </WorkspaceDispatcher>
    );
}
