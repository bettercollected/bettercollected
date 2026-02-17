import React from 'react';
import { getWorkspaceByServerContext } from '@app/lib/server/workspace-auth';
import FormsClient from './FormsClient';
import { notFound } from 'next/navigation';
import { headers } from 'next/headers';
import environments from '@app/configs/environments';
import { Metadata } from 'next';

export async function generateMetadata({
    params
}: {
    params: { workspace_name: string }
}): Promise<Metadata> {
    const workspace = await getWorkspaceByServerContext(params.workspace_name);
    return {
        title: `Forms | ${workspace?.title || workspace?.workspaceName || 'Workspace'}`,
        robots: 'noindex, nofollow'
    };
}

export default async function FormsPage({
    params
}: {
    params: { workspace_name: string }
}) {
    const workspace = await getWorkspaceByServerContext(params.workspace_name);
    if (!workspace) return notFound();

    const headersList = headers();
    const host = headersList.get('host') || '';
    const hasCustomDomain = host !== environments.CLIENT_DOMAIN && host !== environments.ADMIN_DOMAIN;

    return <FormsClient workspace={workspace} hasCustomDomain={hasCustomDomain} />;
}
