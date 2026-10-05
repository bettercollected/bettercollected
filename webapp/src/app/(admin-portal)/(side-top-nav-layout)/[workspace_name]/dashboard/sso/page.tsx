'use client';

import WorkspaceScimSection from '@app/components/workspace-sso/workspace-scim-section';
import WorkspaceSsoSection from '@app/components/workspace-sso/workspace-sso-section';
import { useWorkspacePermissions } from '@app/lib/hooks/use-workspace-permissions';
import { ssoEnabled } from '@app/lib/sso';
import { WorkspacePermission } from '@app/models/enums/workspace-permission';

/**
 * Single sign-on (docs/sso.md): connect the organisation's identity provider
 * (SAML or OIDC) for its verified email domains, and optionally require it;
 * and directory sync (SCIM), which provisions and deprovisions members.
 */
export default function WorkspaceSsoPage() {
    const { can } = useWorkspacePermissions();

    if (!ssoEnabled) {
        return (
            <div className="px-5 py-6 lg:px-10">
                <p className="text-sm text-black-500">Single sign-on is not enabled on this instance.</p>
            </div>
        );
    }

    if (!can(WorkspacePermission.SECURITY_MANAGE)) {
        return (
            <div className="px-5 py-6 lg:px-10">
                <p className="text-sm text-black-500">Only workspace admins can manage single sign-on.</p>
            </div>
        );
    }

    return (
        <div className="flex w-full max-w-[860px] flex-col gap-8 px-5 py-6 lg:px-10">
            <p className="max-w-[62ch] text-sm leading-relaxed text-black-600">
                Let your members sign in with your organisation&apos;s identity provider. People who sign in this way for the first time join this workspace automatically, as long as there is a free seat. Your identity provider decides who that is, so only
                connect one you control.
            </p>
            <WorkspaceSsoSection />
            <WorkspaceScimSection />
        </div>
    );
}
