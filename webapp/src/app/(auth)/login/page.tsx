import environments from '@app/configs/environments';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { isRedirectError } from 'next/dist/client/components/redirect-error';
import { cookies, headers } from 'next/headers';
import { redirect } from 'next/navigation';
import LoginView from '../_components/login-view';

export default async function LoginPage({ searchParams }: { searchParams: { redirect_to?: string; type?: string; workspace_id?: string } }) {

    const headerList = await headers();
    const host = headerList.get('x-forwarded-host') || headerList.get('host') || '';

    const cookieStore = await cookies();
    const authCookie = cookieStore.get('Authorization');
    const refreshCookie = cookieStore.get('RefreshToken');
    const cookieHeader = `${authCookie ? `Authorization=${authCookie.value};` : ''}${refreshCookie ? `RefreshToken=${refreshCookie.value};` : ''}`;

    try {
        const userStatus = await fetch(`${environments.INTERNAL_DOCKER_API_ENDPOINT_HOST}/auth/status`, {
            method: 'GET',
            headers: {
                cookie: cookieHeader
            },
            cache: 'no-store'
        });

        if (userStatus.ok) {
            if (host === environments.ADMIN_DOMAIN) {
                const user = await userStatus.json();
                if (user?.roles?.includes('FORM_CREATOR')) {
                    const userWorkspaceResponse = await fetch(`${environments.INTERNAL_DOCKER_API_ENDPOINT_HOST}/workspaces/mine`, {
                        method: 'GET',
                        headers: {
                            cookie: cookieHeader
                        },
                        cache: 'no-store'
                    });

                    if (userWorkspaceResponse.ok) {
                        const userWorkspaces = await userWorkspaceResponse.json();
                        const defaultWorkspace = (userWorkspaces as WorkspaceDto[]).find((w) => w.ownerId === user.id && w.default);
                        const redirectWorkspace = defaultWorkspace || (userWorkspaces as WorkspaceDto[])[0];

                        if (redirectWorkspace) {
                            if (!redirectWorkspace.title || redirectWorkspace.title === '' || redirectWorkspace.title.toLowerCase() === 'untitled') {
                                return redirect(`/${redirectWorkspace.workspaceName}/onboarding`);
                            }
                            return redirect(`/${redirectWorkspace.workspaceName}/dashboard/forms`);
                        }
                    }
                }
            } else {
                const { redirect_to } = await searchParams;
                if (redirect_to)
                    redirect(redirect_to);
            }
        }
    } catch (e) {
        if (isRedirectError(e)) {
            throw e;
        }
        console.error('Error during server-side auth check:', e);
    }

    return <LoginView />;
}
