import { cookies, headers } from 'next/headers';
import environments from '@app/configs/environments';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';

export async function getWorkspaceByServerContext(workspaceName: string) {
    const cookieStore = cookies();
    const authCookie = cookieStore.get('Authorization');
    const refreshCookie = cookieStore.get('RefreshToken');
    const cookieHeader = `${authCookie ? `Authorization=${authCookie.value};` : ''}${refreshCookie ? `RefreshToken=${refreshCookie.value};` : ''}`;

    const config = {
        method: 'GET',
        headers: {
            cookie: cookieHeader
        },
        next: { revalidate: 0 }
    };

    try {
        const workspaceResponse = await fetch(
            `${environments.INTERNAL_DOCKER_API_ENDPOINT_HOST}/workspaces?workspace_name=${workspaceName}`,
            config
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
    const cookieStore = cookies();
    const authCookie = cookieStore.get('Authorization');
    const refreshCookie = cookieStore.get('RefreshToken');
    const cookieHeader = `${authCookie ? `Authorization=${authCookie.value};` : ''}${refreshCookie ? `RefreshToken=${refreshCookie.value};` : ''}`;

    const config = {
        method: 'GET',
        headers: {
            cookie: cookieHeader
        },
        next: { revalidate: 0 }
    };

    try {
        const userStatusResponse = await fetch(
            `${environments.INTERNAL_DOCKER_API_ENDPOINT_HOST}/auth/status`,
            config
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
