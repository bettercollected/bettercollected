import environments from '@app/configs/environments';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { isRedirectError } from 'next/dist/client/components/redirect-error';
import { cookies } from 'next/headers';
import { redirect } from 'next/navigation';
import LoginView from '../_components/login-view';

export default async function LoginPage() {
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
            next: { revalidate: 0 }
        });

        if (userStatus.ok) {
            const user = await userStatus.json();
            if (user?.roles?.includes('FORM_CREATOR')) {
                const userWorkspaceResponse = await fetch(`${environments.INTERNAL_DOCKER_API_ENDPOINT_HOST}/workspaces/mine`, {
                    method: 'GET',
                    headers: {
                        cookie: cookieHeader
                    },
                    next: { revalidate: 0 }
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
        }
    } catch (e) {
        if (isRedirectError(e)) {
            throw e;
        }
        console.error('Error during server-side auth check:', e);
    }

    return <LoginView />;
}
