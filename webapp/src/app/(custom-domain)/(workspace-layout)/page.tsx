import environments from '@app/configs/environments';
import { headers } from 'next/headers';
import { notFound, redirect } from 'next/navigation';

async function getWorkspaceByDomain(domain: string) {
    try {
        const response = await fetch(`${environments.INTERNAL_DOCKER_API_ENDPOINT_HOST}/workspaces?custom_domain=${domain}`, {
            cache: 'no-store' // Cache for 1 second
        });
        if (!response.ok) return null;
        const data = await response.json();
        return Array.isArray(data) ? data[0] : data;
    } catch (error) {
        console.error('Error fetching workspace by domain:', error);
        return null;
    }
}

export default async function RootPage() {
    const headerList = await headers();
    const host = headerList.get('x-forwarded-host') || headerList.get('host') || '';

    const hasCustomDomain = host !== environments.DASHBOARD_DOMAIN && host !== environments.FORM_DOMAIN;

    if (hasCustomDomain) {
        const workspace = await getWorkspaceByDomain(host);

        if (!workspace?.id) {
            notFound();
        }

        redirect('/forms');
    }

    // Special case for client domain - redirect to admin domain
    if (host === environments.FORM_DOMAIN) {
        const protocol = headerList.get('x-forwarded-proto') || 'https';
        redirect(`${protocol}://${environments.DASHBOARD_DOMAIN}`);
    }

    // Default behavior for admin domain: go to login
    redirect('/login');
}
