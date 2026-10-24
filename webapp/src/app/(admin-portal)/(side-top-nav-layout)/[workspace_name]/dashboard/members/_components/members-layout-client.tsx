'use client';

import React from 'react';

import MembersIcon from '@Components/icons/members';
import { useTranslation } from 'react-i18next';

import RouteTabBar from '@app/components/ui/route-tab-bar';
import { members } from '@app/constants/locales/members';
import { workspaceSectionLabels } from '@app/lib/workspace-sections';

export default function MembersLayout({ children, params }: { children: React.ReactNode; params: { workspace_name: string } }) {
    const { t } = useTranslation();
    const base = `/${params?.workspace_name}/dashboard/members`;

    const tabs = [
        {
            key: 'collaborators',
            icon: <MembersIcon />,
            label: t(members.collaborators.default),
            href: `${base}/collaborators`
        },
        {
            key: 'pending-requests',
            icon: <MembersIcon />,
            label: t(members.pendingRequests.default),
            href: `${base}/pending-requests`
        }
    ];

    // No page h1 here — the sticky top bar already titles the page, and the
    // section below ("Collaborators (N)") carries the specifics. Selection is
    // the trust-blue underline used across the app.
    return (
        <div className="flex min-w-0 flex-col">
            <RouteTabBar ariaLabel={t(workspaceSectionLabels.membersSections)} tabs={tabs} />
            <div>{children}</div>
        </div>
    );
}
