import { cookies } from 'next/headers';
import { cache } from 'react';

import environments from '@app/configs/environments';
import type { WorkspaceSelection, WorkspaceTarget } from '@app/lib/workspace-selection';

async function getCookieHeader() {
    const cookieStore = await cookies();
    const auth = cookieStore.get('Authorization')?.value;
    const refresh = cookieStore.get('RefreshToken')?.value;
    return [auth ? `Authorization=${auth}` : '', refresh ? `RefreshToken=${refresh}` : ''].filter(Boolean).join(';');
}

export async function getWorkspaceByName(name: string) {
    if (!name) return null;
    try {
        const cookieHeader = await getCookieHeader();
        const response = await fetch(`${environments.INTERNAL_DOCKER_API_ENDPOINT_HOST}/workspaces?workspace_name=${name}`, {
            headers: {
                cookie: cookieHeader
            },
            cache: 'no-store'
        });

        if (!response.ok) return null;
        const data = await response.json();
        return Array.isArray(data) ? data[0] : data;
    } catch (error) {
        console.error('Error fetching workspace', error);
        return null;
    }
}

export async function getWorkspaceByDomain(domain: string) {
    if (!domain) return null;
    try {
        const cookieHeader = await getCookieHeader();
        const response = await fetch(`${environments.INTERNAL_DOCKER_API_ENDPOINT_HOST}/workspaces?custom_domain=${domain}`, {
            headers: {
                cookie: cookieHeader
            },
            cache: 'no-store'
        });

        if (!response.ok) return null;
        const data = await response.json();
        return Array.isArray(data) ? data[0] : data;
    } catch (error) {
        console.error('Error fetching workspace', error);
        return null;
    }
}

export async function getWorkspaceById(workspaceId: string) {
    if (!workspaceId) return null;
    try {
        const cookieHeader = await getCookieHeader();
        const response = await fetch(`${environments.INTERNAL_DOCKER_API_ENDPOINT_HOST}/workspaces/${workspaceId}`, {
            headers: {
                cookie: cookieHeader
            },
            cache: 'no-store'
        });

        if (!response.ok) return null;
        return await response.json();
    } catch (error) {
        console.error('Error fetching workspace', error);
        return null;
    }
}

// `published` asks for the published version, which anyone may read; without
// it the API returns the draft, which only workspace members may read.
export async function getFormById(workspaceId: string, formId: string, { published = false }: { published?: boolean } = {}) {
    if (!workspaceId || !formId) return null;
    try {
        const cookieHeader = await getCookieHeader();
        const query = published ? '?published=true' : '';
        const response = await fetch(`${environments.INTERNAL_DOCKER_API_ENDPOINT_HOST}/workspaces/${workspaceId}/forms/${formId}${query}`, {
            headers: {
                cookie: cookieHeader
            },
            cache: 'no-store'
        });

        if (!response.ok) return null;
        return await response.json();
    } catch (error) {
        console.error('Error fetching form', error);
        return null;
    }
}

/**
 * The signed-in user (GET /auth/status), or null. Asked once per server
 * render: the dashboard's nested layouts and pages share the answer.
 */
export const getUser = cache(async () => {
    try {
        const cookieHeader = await getCookieHeader();
        const response = await fetch(`${environments.INTERNAL_DOCKER_API_ENDPOINT_HOST}/auth/status`, {
            headers: {
                cookie: cookieHeader
            },
            cache: 'no-store'
        });

        if (!response.ok) return null;
        return await response.json();
    } catch (error) {
        console.error('Error fetching user', error);
        return null;
    }
});

/**
 * The workspace selection after sign-in (GET /workspaces/mine/selection):
 * the workspaces the signed-in user may open and, for a sign-in that
 * started from `next` (a workspace dashboard page), whether to go there.
 * `null` when the server couldn't answer (signed out, or unreachable).
 */
export async function getWorkspaceSelection(next?: string | null): Promise<WorkspaceSelection | null> {
    try {
        const cookieHeader = await getCookieHeader();
        const query = next ? `?${new URLSearchParams({ next }).toString()}` : '';
        const response = await fetch(`${environments.INTERNAL_DOCKER_API_ENDPOINT_HOST}/workspaces/mine/selection${query}`, {
            headers: {
                cookie: cookieHeader
            },
            cache: 'no-store'
        });
        if (!response.ok) return null;
        return (await response.json()) as WorkspaceSelection;
    } catch (error) {
        console.error('Error fetching the workspace selection', error);
        return null;
    }
}

/**
 * Where `next` (a workspace dashboard path) goes for the signed-in user
 * (GET /workspaces/mine/selection/target): the dashboard's check on every
 * workspace page. `status` 401: nobody is signed in; any other failure
 * (the API down, a timeout, an over-long handle) comes back as `data: null`.
 */
export async function getWorkspaceTarget(next: string): Promise<{ status: number; data: WorkspaceTarget | null }> {
    try {
        const cookieHeader = await getCookieHeader();
        const response = await fetch(`${environments.INTERNAL_DOCKER_API_ENDPOINT_HOST}/workspaces/mine/selection/target?${new URLSearchParams({ next }).toString()}`, {
            headers: {
                cookie: cookieHeader
            },
            cache: 'no-store'
        });
        if (!response.ok) return { status: response.status, data: null };
        return { status: response.status, data: (await response.json()) as WorkspaceTarget };
    } catch (error) {
        console.error('Error checking the workspace target', error);
        return { status: 0, data: null };
    }
}

export async function getGroupById(workspaceId: string, groupId: string) {
    if (!workspaceId || !groupId) return null;
    try {
        const cookieHeader = await getCookieHeader();
        const response = await fetch(`${environments.INTERNAL_DOCKER_API_ENDPOINT_HOST}/workspaces/${workspaceId}/groups/${groupId}`, {
            headers: {
                cookie: cookieHeader
            },
            cache: 'no-store'
        });

        if (!response.ok) return null;
        return await response.json();
    } catch (error) {
        console.error('Error fetching group', error);
        return null;
    }
}
