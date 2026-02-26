import environments from '@app/configs/environments';
import { getWorkspaceByDomain } from '@app/lib/server/api';
import { headers } from 'next/headers';
import { notFound, redirect } from 'next/navigation';

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
