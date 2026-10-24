import React from 'react';

import MembersIcon from '@Components/icons/members';
import { LockKeyhole, Palette, ShieldCheck, Sparkles } from 'lucide-react';

import { members } from '@app/constants/locales/members';
import { Can, dashboardUrl, defaultAiTabUrl, workspaceSectionLabels, workspaceSectionUrls } from '@app/lib/workspace-sections';
import { WorkspacePermission } from '@app/models/enums/workspace-permission';
import { INavbarItem } from '@app/models/props/navbar';

interface WorkspaceNavOptions {
    workspaceName?: string;
    t: (key: string) => string;
    can: Can;
    ssoEnabled: boolean;
}

/**
 * The sidebar's Workspace group: Members, Themes, Single sign-on, AI. The
 * drawer hides an item from members without its permission (the API refuses
 * them anyway); AI has no permission, every member has Memory and Settings.
 */
export function workspaceNavItems({ workspaceName, t, can, ssoEnabled }: WorkspaceNavOptions): Array<INavbarItem> {
    const base = dashboardUrl(workspaceName);
    const urls = workspaceSectionUrls(workspaceName);
    const iconClass = 'h-5 w-5 stroke-2';

    return [
        {
            key: 'members',
            name: t(members.default),
            url: `${base}/members`,
            permission: WorkspacePermission.MEMBERS_MANAGE,
            icon: <MembersIcon />
        },
        {
            key: 'themes',
            name: t(workspaceSectionLabels.themes),
            url: `${base}/themes`,
            permission: WorkspacePermission.WORKSPACE_MANAGE,
            icon: <Palette className={iconClass} />
        },
        // Single sign-on with its Domains tab. Without SSO on this instance
        // the section is only the verified domains, and is named for them.
        ssoEnabled
            ? {
                  key: 'sso',
                  name: t(workspaceSectionLabels.sso),
                  url: urls.sso,
                  permission: WorkspacePermission.SECURITY_MANAGE,
                  icon: <LockKeyhole className={iconClass} />
              }
            : {
                  key: 'domains',
                  name: t(workspaceSectionLabels.domains),
                  url: urls.domains,
                  activePath: urls.sso,
                  permission: WorkspacePermission.SECURITY_MANAGE,
                  icon: <ShieldCheck className={iconClass} />
              },
        {
            // Opens the first tab this member may use: Profile for those who
            // manage AI, Memory for everyone else.
            key: 'ai',
            name: t(workspaceSectionLabels.ai),
            url: defaultAiTabUrl(workspaceName, can),
            activePath: urls.ai,
            icon: <Sparkles className={iconClass} />
        }
    ];
}
