import environments from '@app/configs/environments';
import fetchWithCookies from '@app/utils/fetch-utils';
import { cookies, headers } from 'next/headers';
import { notFound, redirect } from 'next/navigation';
import OnboardingClient from './_components/onbaording-client';

async function getWorkspaceByName(name: string) {
    return await fetchWithCookies(`${environments.INTERNAL_DOCKER_API_ENDPOINT_HOST}/workspaces?workspace_name=${name}`, { cache: 'no-store' });
}

async function getAuthStatus(cookieStore: any) {
    const auth = cookieStore.get('Authorization')?.value;
    const refresh = cookieStore.get('RefreshToken')?.value;

    if (!auth) return null;

    try {
        return await fetchWithCookies(`${environments.INTERNAL_DOCKER_API_ENDPOINT_HOST}/auth/status`, {
            headers: {
                cookie: `Authorization=${auth}; RefreshToken=${refresh}`
            }
        });
    } catch (error) {
        return null;
    }
}

export default async function OnboardingPage(props: { params: Promise<{ workspace_name: string }> }) {
    const params = await props.params;
    const headerList = await headers();
    const cookieStore = await cookies();
    const host = headerList.get('x-forwarded-host') || headerList.get('host') || '';

    const isCustomDomain = host !== environments.DASHBOARD_DOMAIN && host !== environments.FORM_DOMAIN;

    if (isCustomDomain) {
        redirect('/');
    }

    const user = await getAuthStatus(cookieStore);
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
