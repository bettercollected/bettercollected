import { redirect } from 'next/navigation';

import { readRuntimeFlags } from '@app/lib/runtime-flags';
import { workspaceSectionUrls } from '@app/lib/workspace-sections';

import WorkspaceSsoPage from './_components/sso-page-client';

/**
 * The Single sign-on tab. Without SSO on this instance (SSO_ENABLED, read per
 * request) the section is only Domains, so this address goes there instead of
 * a "not available" page.
 */
export default async function Page({ params }: { params: Promise<{ workspace_name: string }> }) {
    const { workspace_name } = await params;
    if (!readRuntimeFlags().ssoEnabled) {
        redirect(workspaceSectionUrls(workspace_name).domains);
    }
    return <WorkspaceSsoPage />;
}
