import { Metadata } from 'next';
import { redirect } from 'next/navigation';

import WorkspaceSelectView from '@app/components/workspace-select/workspace-select-view';
import { getUser } from '@app/lib/server/api';
import { NO_ACCESS_NOTICE } from '@app/lib/workspace-selection';

export const metadata: Metadata = {
    title: 'Choose a workspace',
    robots: 'noindex, nofollow'
};

/**
 * The workspace selection screen: after a sign-in with a real choice, after a
 * link to a workspace the user can't open, and from the workspace switcher.
 */
export default async function SelectWorkspacePage({ searchParams }: { searchParams: Promise<{ notice?: string | string[] }> }) {
    const user = await getUser();
    if (!user) {
        redirect('/login');
    }
    const { notice } = await searchParams;
    // only the one fixed code: nothing from the URL is shown
    const shown = (Array.isArray(notice) ? notice[0] : notice) === NO_ACCESS_NOTICE ? NO_ACCESS_NOTICE : null;
    return <WorkspaceSelectView notice={shown} />;
}
