import { WorkspacePermission } from '@app/models/enums/workspace-permission';

// The dashboard's Workspace sections that group several pages behind tabs:
// Single sign-on (sso, domains) and AI (profile, memory, mcp, settings).
// Which tabs a member sees follows their permissions; the API refuses the
// same calls on its own, the UI only hides what would be refused.

export type Can = (permission: WorkspacePermission) => boolean;

export interface SectionTab {
    key: string;
    /** Translation key of the tab label (public/locales/<lang>/common.json). */
    labelKey: string;
    href: string;
    /** Active on this exact path only: its href prefixes the other tabs. */
    exact?: boolean;
}

interface TabDefinition {
    key: string;
    labelKey: string;
    path: string;
    exact?: boolean;
    /** Needed to see the tab; none means every member. */
    permission?: WorkspacePermission;
}

export const workspaceSectionLabels = {
    themes: 'WORKSPACE_SECTIONS.THEMES',
    sso: 'WORKSPACE_SECTIONS.SSO',
    domains: 'WORKSPACE_SECTIONS.DOMAINS',
    ai: 'WORKSPACE_SECTIONS.AI',
    aiProfile: 'WORKSPACE_SECTIONS.AI_PROFILE',
    aiMemory: 'WORKSPACE_SECTIONS.AI_MEMORY',
    aiMcp: 'WORKSPACE_SECTIONS.AI_MCP',
    aiSettings: 'WORKSPACE_SECTIONS.AI_SETTINGS',
    membersSections: 'WORKSPACE_SECTIONS.MEMBERS_SECTIONS',
    ssoSections: 'WORKSPACE_SECTIONS.SSO_SECTIONS',
    aiSections: 'WORKSPACE_SECTIONS.AI_SECTIONS',
    verifyDomain: 'WORKSPACE_SECTIONS.VERIFY_DOMAIN'
} as const;

export const dashboardUrl = (workspaceName?: string) => `/${workspaceName ?? ''}/dashboard`;

/** Every page of the two sections, for links from elsewhere in the app. */
export const workspaceSectionUrls = (workspaceName?: string) => {
    const base = dashboardUrl(workspaceName);
    return {
        sso: `${base}/sso`,
        domains: `${base}/sso/domains`,
        ai: `${base}/ai`,
        aiProfile: `${base}/ai/profile`,
        aiMemory: `${base}/ai/memory`,
        aiMcp: `${base}/ai/mcp`,
        aiSettings: `${base}/ai/settings`
    };
};

const AI_TABS: Array<TabDefinition> = [
    { key: 'profile', labelKey: workspaceSectionLabels.aiProfile, path: 'ai/profile', permission: WorkspacePermission.AI_MANAGE },
    // Per user, for every member: what the assistant remembers about them.
    { key: 'memory', labelKey: workspaceSectionLabels.aiMemory, path: 'ai/memory' },
    // The MCP endpoint and the API keys (the same keys serve the REST API and SDKs).
    { key: 'mcp', labelKey: workspaceSectionLabels.aiMcp, path: 'ai/mcp', permission: WorkspacePermission.SECURITY_MANAGE },
    // Every member sees whether AI is on and sets "Learn my preferences";
    // only admins change the workspace opt-in.
    { key: 'settings', labelKey: workspaceSectionLabels.aiSettings, path: 'ai/settings' }
];

const SSO_TABS: Array<TabDefinition & { needsSso?: boolean }> = [
    { key: 'sso', labelKey: workspaceSectionLabels.sso, path: 'sso', exact: true, permission: WorkspacePermission.SECURITY_MANAGE, needsSso: true },
    { key: 'domains', labelKey: workspaceSectionLabels.domains, path: 'sso/domains', permission: WorkspacePermission.SECURITY_MANAGE }
];

const toTab = (base: string, { key, labelKey, path, exact }: TabDefinition): SectionTab => ({ key, labelKey, href: `${base}/${path}`, ...(exact ? { exact } : {}) });

/** The AI tabs this member may use, in order: Profile, Memory, MCP, Settings. */
export function aiTabs(workspaceName: string | undefined, can: Can): Array<SectionTab> {
    const base = dashboardUrl(workspaceName);
    return AI_TABS.filter((tab) => !tab.permission || can(tab.permission)).map((tab) => toTab(base, tab));
}

/** Where the AI menu opens: the first tab this member may use (Memory for most members). */
export function defaultAiTabUrl(workspaceName: string | undefined, can: Can): string {
    return aiTabs(workspaceName, can)[0]?.href ?? workspaceSectionUrls(workspaceName).aiMemory;
}

/** The Single sign-on tabs this member may use; without SSO only Domains is left. */
export function ssoTabs(workspaceName: string | undefined, can: Can, ssoEnabled: boolean): Array<SectionTab> {
    const base = dashboardUrl(workspaceName);
    return SSO_TABS.filter((tab) => (!tab.needsSso || ssoEnabled) && (!tab.permission || can(tab.permission))).map((tab) => toTab(base, tab));
}

/** Is this tab the current page? */
export function isTabActive(pathname: string | null | undefined, tab: Pick<SectionTab, 'href' | 'exact'>): boolean {
    if (!pathname) return false;
    const path = pathname.length > 1 ? pathname.replace(/\/+$/, '') : pathname;
    return path === tab.href || (!tab.exact && path.startsWith(tab.href + '/'));
}
