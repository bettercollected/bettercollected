import { redirect, notFound } from 'next/navigation';
import { headers } from 'next/headers';
import environments from '@app/configs/environments';
import ResponderPortalLayoutClient from '../[workspace_name]/(portal)/_components/ResponderPortalLayoutClient';
import WorkspaceFormsTabContent from '@Components/dashboard/workspace-forms-tab-content';
import WorkspaceResponsesTabContent from '@Components/dashboard/workspace-responses-tab-content';

/* Helper to get workspace by domain */
async function getWorkspaceByDomain(domain: string) {
    try {
        const response = await fetch(`${environments.INTERNAL_DOCKER_API_ENDPOINT_HOST}/workspaces?custom_domain=${domain}`, {
            next: { revalidate: 300 }
        });
        if (!response.ok) return null;
        return await response.json();
    } catch (error) {
        console.error('Error fetching workspace by domain:', error);
        return null;
    }
}

async function getAuthUser(cookieHeader: string) {
    // ... logic to verify user if needed, or pass auth via client ...
    // The client component uses useAppSelector(selectAuth) which is populated by ReduxWrapperAppRouter/Layout
    // But server-side check might be good. For now, rely on client or layout wrapper.
    return null;
}

export default async function CustomDomainTabHandler({ params, searchParams }: { params: any, searchParams: any }) {
    const headerList = await headers();
    const host = headerList.get('x-forwarded-host') || headerList.get('host') || '';

    // Check if it's admin or client domain. If so, let [workspace_name] handle it (if the route is dynamic)
    // But since this is a catch-all or specific static route, we need to be careful.

    // Actually, creating specific files app/forms/page.tsx is safer.
    return notFound();
}
