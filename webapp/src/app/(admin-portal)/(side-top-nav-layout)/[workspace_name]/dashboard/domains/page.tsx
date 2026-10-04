'use client';

import WorkspaceDomainsSection from '@app/components/workspace-domains/workspace-domains-section';
import { useWorkspacePermissions } from '@app/lib/hooks/use-workspace-permissions';
import { WorkspacePermission } from '@app/models/enums/workspace-permission';

/**
 * Verified email domains (docs/verified-domains.md): prove the workspace owns
 * an email domain with a DNS TXT record. Single sign-on will only accept
 * domains verified here.
 */
export default function WorkspaceDomainsPage() {
    const { can } = useWorkspacePermissions();

    if (!can(WorkspacePermission.SECURITY_MANAGE)) {
        return (
            <div className="px-5 py-6 lg:px-10">
                <p className="text-sm text-black-500">Only workspace admins can manage domains.</p>
            </div>
        );
    }

    return (
        <div className="flex w-full max-w-[760px] flex-col gap-8 px-5 py-6 lg:px-10">
            <p className="max-w-[62ch] text-sm leading-relaxed text-black-600">
                Verify the email domains your organisation owns. Single sign-on can only be set up for a verified domain, and once it is, your identity provider decides who can sign in with an address on that domain. A domain can be verified by one
                workspace at a time.
            </p>
            <WorkspaceDomainsSection />
        </div>
    );
}
