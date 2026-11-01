import { Metadata } from 'next';
import { redirect } from 'next/navigation';

import WorkspaceSelectView from '@app/components/workspace-select/workspace-select-view';
import { getUser } from '@app/lib/server/api';
import { knownNotice } from '@app/lib/workspace-selection';

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
    // only the fixed codes: nothing from the URL is shown
    const shown = knownNotice(Array.isArray(notice) ? notice[0] : notice);
    return <WorkspaceSelectView notice={shown} />;
}
