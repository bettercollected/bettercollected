'use client';

import { useTranslation } from 'react-i18next';

import WorkspaceScimSection from '@app/components/workspace-sso/workspace-scim-section';
import WorkspaceSsoSection from '@app/components/workspace-sso/workspace-sso-section';
import { useWorkspacePermissions } from '@app/lib/hooks/use-workspace-permissions';
import { WorkspacePermission } from '@app/models/enums/workspace-permission';

/**
 * Single sign-on (docs/sso.md): connect the organisation's identity provider
 * (SAML or OIDC) for its verified email domains, and optionally require it;
 * and directory sync (SCIM), which provisions and deprovisions members.
 * The page sends instances without SSO to the Domains tab before this renders.
 */
export default function WorkspaceSsoPage() {
    const { t } = useTranslation();
    const { can } = useWorkspacePermissions();

    if (!can(WorkspacePermission.SECURITY_MANAGE)) {
        return (
            <div className="pb-10">
                <p className="text-sm text-black-600">{t('SSO_UI.ONLY_ADMINS')}</p>
            </div>
        );
    }

    return (
        <div className="flex w-full max-w-[860px] flex-col gap-8 pb-10">
            <p className="max-w-[62ch] text-sm leading-relaxed text-black-600">
                {t('SSO_UI.PAGE_INTRO')}
            </p>
            <WorkspaceSsoSection />
            <WorkspaceScimSection />
        </div>
    );
}
