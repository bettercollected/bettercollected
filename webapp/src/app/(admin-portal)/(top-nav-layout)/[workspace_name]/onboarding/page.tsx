import environments from '@app/configs/environments';
import { getUser, getWorkspaceByName } from '@app/lib/server/api';
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

    const user = await getUser();
    console.log('OnboardingPage user:', user);
    if (!user) {
        // redirect('/login');
    }

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
