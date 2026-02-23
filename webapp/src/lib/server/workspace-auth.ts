import environments from '@app/configs/environments';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { cookies } from 'next/headers';

export async function getWorkspaceByServerContext(workspaceName: string) {
    const cookieStore = await cookies();
    const authCookie = cookieStore.get('Authorization');
    const refreshCookie = cookieStore.get('RefreshToken');
    const cookieHeader = `${authCookie ? `Authorization=${authCookie.value};` : ''}${refreshCookie ? `RefreshToken=${refreshCookie.value};` : ''}`;


    try {
        const workspaceResponse = await fetch(
            `${environments.INTERNAL_DOCKER_API_ENDPOINT_HOST}/workspaces?workspace_name=${workspaceName}`,
            {
                method: 'GET',
                headers: {
                    cookie: cookieHeader
                },
                cache: 'no-store'
            }
        );
        if (!workspaceResponse.ok) return null;
        const workspace: WorkspaceDto = await workspaceResponse.json();
        return workspace;
    } catch (e) {
        console.error('Error fetching workspace:', e);
        return null;
    }
}

export async function checkUserWorkspaceAuth(workspace: WorkspaceDto) {
    const cookieStore = await cookies();
    const authCookie = cookieStore.get('Authorization');
    const refreshCookie = cookieStore.get('RefreshToken');
    const cookieHeader = `${authCookie ? `Authorization=${authCookie.value};` : ''}${refreshCookie ? `RefreshToken=${refreshCookie.value};` : ''}`;

    try {
        const userStatusResponse = await fetch(
            `${environments.INTERNAL_DOCKER_API_ENDPOINT_HOST}/auth/status`,
            {
                method: 'GET',
                headers: {
                    cookie: cookieHeader
                },
                cache: 'no-store'
            }
        );
        if (!userStatusResponse.ok) return false;
        const user = await userStatusResponse.json();

        if (!user?.roles?.includes('FORM_CREATOR') || !workspace.dashboardAccess) {
            return false;
        }
        return true;
    } catch (e) {
        console.error('Error checking user auth:', e);
        return false;
    }
}
