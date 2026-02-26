import environments from '@app/configs/environments';
import { cookies } from 'next/headers';

async function getCookieHeader() {
    const cookieStore = await cookies();
    const auth = cookieStore.get('Authorization')?.value;
    const refresh = cookieStore.get('RefreshToken')?.value;
    return [
        auth ? `Authorization=${auth}` : '',
        refresh ? `RefreshToken=${refresh}` : ''
    ].filter(Boolean).join(';');
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

export async function getUser() {
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
    }
}
