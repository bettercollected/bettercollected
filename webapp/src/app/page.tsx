import { headers } from 'next/headers';
import { redirect, notFound } from 'next/navigation';
import environments from '@app/configs/environments';
import ResponderPortalContainer from '@Components/RespondersPortal/ResponderPortalContainer';

async function getWorkspaceByDomain(domain: string) {
    try {
        const response = await fetch(`${environments.INTERNAL_DOCKER_API_ENDPOINT_HOST}/workspaces?custom_domain=${domain}`, {
            next: { revalidate: 300 } // Cache for 5 minutes
        });
        if (!response.ok) return null;
        return await response.json();
    } catch (error) {
        console.error('Error fetching workspace by domain:', error);
        return null;
    }
}

export default async function RootPage() {
    const headerList = await headers();
    const host = headerList.get('x-forwarded-host') || headerList.get('host') || '';

    const hasCustomDomain = host !== environments.ADMIN_DOMAIN && host !== environments.CLIENT_DOMAIN;

    if (hasCustomDomain) {
        const workspace = await getWorkspaceByDomain(host);

        if (!workspace?.id) {
            notFound();
        }

        return <ResponderPortalContainer workspace={workspace} hasCustomDomain={true} />;
    }

    // Special case for client domain - redirect to admin domain
    if (host === environments.CLIENT_DOMAIN) {
        const protocol = headerList.get('x-forwarded-proto') || 'https';
        redirect(`${protocol}://${environments.ADMIN_DOMAIN}`);
    }

    // Default behavior for admin domain: go to login
    redirect('/login');
}
