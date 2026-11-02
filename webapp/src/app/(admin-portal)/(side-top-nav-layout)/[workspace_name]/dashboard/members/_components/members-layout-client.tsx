'use client';

import React from 'react';

import MembersIcon from '@Components/icons/members';
import { useTranslation } from 'react-i18next';

import RouteTabBar from '@app/components/ui/route-tab-bar';
import { members } from '@app/constants/locales/members';
import { useWorkspacePermissions } from '@app/lib/hooks/use-workspace-permissions';
import { workspaceSectionLabels } from '@app/lib/workspace-sections';
import { WorkspacePermission } from '@app/models/enums/workspace-permission';

export default function MembersLayout({ children, params }: { children: React.ReactNode; params: { workspace_name: string } }) {
    const { t } = useTranslation();
    const base = `/${params?.workspace_name}/dashboard/members`;
    // Teams: named groups of members that a form's access can name. Owners and admins, and only while the server has form-level access on.
    const { can, formAccessEnabled } = useWorkspacePermissions();
    const showTeams = formAccessEnabled && can(WorkspacePermission.MEMBERS_MANAGE);

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
        },
        ...(showTeams
            ? [
                  {
                      key: 'teams',
                      icon: <MembersIcon />,
                      label: t('STAFF.TEAMS.TAB'),
                      href: `${base}/teams`
                  }
              ]
            : [])
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
