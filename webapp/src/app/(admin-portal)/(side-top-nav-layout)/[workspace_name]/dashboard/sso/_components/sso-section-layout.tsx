'use client';

import React from 'react';

import { useTranslation } from 'react-i18next';

import RouteTabBar from '@app/components/ui/route-tab-bar';
import { useWorkspacePermissions } from '@app/lib/hooks/use-workspace-permissions';
import { ssoTabs, workspaceSectionLabels } from '@app/lib/workspace-sections';
import { useSsoEnabled } from '@app/shared/hocs/runtime-flags-provider';

/**
 * The Single sign-on section: Single sign-on, then Domains (SSO only works
 * for a verified domain). Without SSO on this instance only Domains is left,
 * shown as a plain page without a tab bar.
 */
export default function SSOSectionLayout({ workspaceName, children }: { workspaceName: string; children: React.ReactNode }) {
    const { t } = useTranslation();
    const ssoEnabled = useSsoEnabled();
    const { can } = useWorkspacePermissions();
    const tabs = ssoTabs(workspaceName, can, ssoEnabled).map((tab) => ({ ...tab, label: t(tab.labelKey) }));

    return (
        <div className="flex min-w-0 flex-col">
            <RouteTabBar ariaLabel={t(workspaceSectionLabels.ssoSections)} tabs={tabs} />
            <div>{children}</div>
        </div>
    );
}
