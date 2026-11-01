'use client';

import { useTranslation } from 'react-i18next';

import WorkspaceDomainsSection from '@app/components/workspace-domains/workspace-domains-section';
import { useWorkspacePermissions } from '@app/lib/hooks/use-workspace-permissions';
import { WorkspacePermission } from '@app/models/enums/workspace-permission';

/**
 * Verified email domains (docs/verified-domains.md): prove the workspace owns
 * an email domain with a DNS TXT record. Single sign-on will only accept
 * domains verified here.
 */
export default function WorkspaceDomainsPage() {
    const { t } = useTranslation();
    const { can } = useWorkspacePermissions();

    if (!can(WorkspacePermission.SECURITY_MANAGE)) {
        return (
            <div className="pb-10">
                <p className="text-sm text-black-600">{t('SSO_UI.DOMAINS_ONLY_ADMINS')}</p>
            </div>
        );
    }

    return (
        <div className="flex w-full max-w-[760px] flex-col gap-8 pb-10">
            <p className="max-w-[62ch] text-sm leading-relaxed text-black-600">
                {t('SSO_UI.DOMAINS_PAGE_INTRO')}
            </p>
            <WorkspaceDomainsSection />
        </div>
    );
}
