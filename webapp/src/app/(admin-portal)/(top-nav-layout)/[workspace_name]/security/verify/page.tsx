import { Metadata } from 'next';
import { redirect } from 'next/navigation';

import MfaVerifyView from '@app/components/mfa/mfa-verify-view';
import { getUser } from '@app/lib/server/api';

export const metadata: Metadata = {
    title: 'Second step required',
    robots: 'noindex, nofollow'
};

/**
 * Where a workspace that requires an authenticator app sends a session that has
 * not presented one (the API answers 403 `mfa_required`). Not a dashboard page,
 * and it reads no workspace data: only a signed-in person is needed.
 */
export default async function VerifyPage({ params, searchParams }: { params: Promise<{ workspace_name: string }>; searchParams: Promise<{ next?: string | string[] }> }) {
    const user = await getUser();
    if (!user) {
        redirect('/login');
    }
    const { workspace_name } = await params;
    const { next } = await searchParams;
    return <MfaVerifyView workspaceName={workspace_name} next={Array.isArray(next) ? next[0] : next} />;
}
