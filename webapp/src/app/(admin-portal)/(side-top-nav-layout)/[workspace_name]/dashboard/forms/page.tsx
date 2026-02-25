import environments from '@app/configs/environments';
import { getWorkspaceByServerContext } from '@app/lib/server/workspace-auth';
import { Metadata } from 'next';
import { headers } from 'next/headers';
import { notFound } from 'next/navigation';
import FormsClient from './FormsClient';

export async function generateMetadata(
    props: {
        params: Promise<{ workspace_name: string }>
    }
): Promise<Metadata> {
    const params = await props.params;
    const workspace = await getWorkspaceByServerContext(params.workspace_name);
    return {
        title: `Forms | ${workspace?.title || workspace?.workspaceName || 'Workspace'}`,
        robots: 'noindex, nofollow'
    };
}

export default async function FormsPage(
    props: {
        params: Promise<{ workspace_name: string }>
    }
) {
    const params = await props.params;
    const workspace = await getWorkspaceByServerContext(params.workspace_name);
    if (!workspace) return notFound();

    const headersList = await headers();
    const host = headersList.get('host') || '';
    const hasCustomDomain = host !== environments.FORM_DOMAIN && host !== environments.DASHBOARD_DOMAIN;

    return <FormsClient workspace={workspace} hasCustomDomain={hasCustomDomain} />;
}
