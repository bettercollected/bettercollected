import environments from '@app/configs/environments';
import { getWorkspaceByName } from '@app/lib/server/api';
import { requireWorkspaceAccess } from '@app/lib/server/workspace-gate';
import { headers } from 'next/headers';
import { notFound, redirect } from 'next/navigation';
import OnboardingClient from './_components/onbaording-client';

export default async function OnboardingPage(props: { params: Promise<{ workspace_name: string }> }) {
    const params = await props.params;
    const headerList = await headers();
    const host = headerList.get('x-forwarded-host') || headerList.get('host') || '';

    const isCustomDomain = host !== environments.DASHBOARD_DOMAIN && host !== environments.FORM_DOMAIN;

    if (isCustomDomain) {
        redirect('/');
    }

    // the workspace's members only, and the same answer for a workspace the
    // user isn't in as for one that doesn't exist (the dashboard's check)
    await requireWorkspaceAccess(params.workspace_name);

    const workspace = await getWorkspaceByName(params.workspace_name);

    if (!workspace?.id) {
        return notFound();
    }

    if (workspace.title && workspace.title.toLowerCase() !== 'untitled') {
        redirect(`/${workspace.workspaceName}/dashboard`);
    }

    return (
        <OnboardingClient workspace={workspace} />
    );
}
