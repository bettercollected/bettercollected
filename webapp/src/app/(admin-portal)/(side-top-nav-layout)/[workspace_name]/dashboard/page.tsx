import environments from '@app/configs/environments';
import { cookies, headers } from 'next/headers';
import { notFound, redirect } from 'next/navigation';
import CreatorDashboardClient from './CreatorDashboardClient';
import { getWorkspaceByName } from './layout';

export default async function CreatorDashboardPage({ params }: { params: Promise<{ workspace_name: string }> }) {
    const { workspace_name } = await params;
    const cookieStore = await cookies();
    const headerList = await headers();

    // Check for admin domain
    const host = headerList.get('x-forwarded-host') || headerList.get('host') || '';
    const hasAdminDomain = host === environments.ADMIN_DOMAIN || host === environments.CLIENT_DOMAIN;

    if (!hasAdminDomain) {
        redirect('/');
    }

    const auth = (cookieStore.get('Authorization'))?.value;
    const workspace = await getWorkspaceByName(workspace_name);

    if (!workspace?.id) {
        notFound();
    }

    // In many cases, we also check if they are logged in at all.
    if (!auth) {
        redirect('/login');
    }

    return (
        <CreatorDashboardClient hasCustomDomain={!hasAdminDomain} />
    );
}
