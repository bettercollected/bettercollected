'use client';

import React from 'react';

import { useTranslation } from 'react-i18next';

import RouteTabBar from '@app/components/ui/route-tab-bar';
import { useWorkspacePermissions } from '@app/lib/hooks/use-workspace-permissions';
import { aiTabs, workspaceSectionLabels } from '@app/lib/workspace-sections';

/**
 * The AI section: Profile, Memory, MCP and Settings, each its own route.
 * Only the tabs this member may use are rendered.
 */
export default function AISectionLayout({ workspaceName, children }: { workspaceName: string; children: React.ReactNode }) {
    const { t } = useTranslation();
    const { can, ready } = useWorkspacePermissions();
    const tabs = aiTabs(workspaceName, can).map((tab) => ({ ...tab, label: t(tab.labelKey) }));

    return (
        <div className="flex min-w-0 flex-col">
            {/* Wait for the permissions, so admin tabs don't pop in after the rest. */}
            {!ready ? <div aria-hidden="true" className="mb-[38px] h-[45px] border-b border-black-400" /> : <RouteTabBar ariaLabel={t(workspaceSectionLabels.aiSections)} tabs={tabs} />}
            <div>{children}</div>
        </div>
    );
}
