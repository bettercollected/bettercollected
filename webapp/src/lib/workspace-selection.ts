// The workspace selection screen after sign-in. The server decides what the
// user may open (GET /workspaces/mine/selection); this module only decides
// where the browser goes with that answer and in which order the rows show.

/** One workspace the signed-in user may pick (the server's list only). */
export interface WorkspaceChoice {
    id: string;
    title?: string | null;
    workspaceName: string;
    profileImage?: string | null;
    role?: string | null;
    isOwner: boolean;
    customDomain?: string | null;
    disabled: boolean;
    ssoRequired: boolean;
}

export interface WorkspaceSelection {
    workspaces: WorkspaceChoice[];
    canCreateWorkspace: boolean;
    isCreator: boolean;
    /** a workspace dashboard page the sign-in started from, which the user may open */
    next?: string | null;
    /** `no_access`: the sign-in started from a workspace page the user can't open (or that doesn't exist) */
    notice?: string | null;
}

export const SELECT_WORKSPACE_PATH = '/workspace/select';

/** The one notice the screen knows: a fixed code, never text from the URL. */
export const NO_ACCESS_NOTICE = 'no_access';

/** Show the search once the list is longer than this. */
export const SEARCH_THRESHOLD = 8;

export function selectWorkspaceUrl(notice?: string | null): string {
    return notice === NO_ACCESS_NOTICE ? `${SELECT_WORKSPACE_PATH}?notice=${NO_ACCESS_NOTICE}` : SELECT_WORKSPACE_PATH;
}

/** The dashboard of the workspace with handle `name` (a route param, decoded or not). */
export function workspaceDashboardPath(name: string): string {
    let decoded = name;
    try {
        decoded = decodeURIComponent(name);
    } catch {
        // not percent-encoded after all
    }
    return `/${encodeURIComponent(decoded)}/dashboard`;
}

export function isUntitled(title?: string | null): boolean {
    return !title || title.trim() === '' || title.trim().toLowerCase() === 'untitled';
}

/** Where opening a workspace goes: its forms, or the onboarding of an owner's untitled workspace. */
export function workspaceHome(choice: Pick<WorkspaceChoice, 'workspaceName' | 'title' | 'isOwner'>): string {
    const name = encodeURIComponent(choice.workspaceName);
    if (choice.isOwner && isUntitled(choice.title)) return `/${name}/onboarding`;
    return `/${name}/dashboard/forms`;
}

/**
 * Where a signed-in user goes from the sign-in page:
 * - the page the sign-in started from, when the server allowed it;
 * - the selection screen with the notice, when that page is in a workspace
 *   they can't open;
 * - straight into their only workspace (unless it needs its single sign-on);
 * - otherwise the selection screen (no workspace, or a real choice).
 */
export function postSignInDestination(selection: WorkspaceSelection): string {
    if (selection.next) return selection.next;
    if (selection.notice) return selectWorkspaceUrl(selection.notice);
    const [only, ...rest] = selection.workspaces;
    if (only && rest.length === 0 && !only.ssoRequired) return workspaceHome(only);
    return SELECT_WORKSPACE_PATH;
}

/** The rows in order: the last-used workspace first, the rest as the server sorted them (by name). */
export function orderChoices(workspaces: WorkspaceChoice[], lastUsedId?: string | null): WorkspaceChoice[] {
    const last = lastUsedId ? workspaces.find((w) => w.id === lastUsedId) : undefined;
    if (!last) return workspaces;
    return [last, ...workspaces.filter((w) => w !== last)];
}

export function matchesSearch(choice: WorkspaceChoice, query: string): boolean {
    const needle = query.trim().toLowerCase();
    if (!needle) return true;
    return [choice.title, choice.workspaceName, choice.customDomain].some((value) => !!value && value.toLowerCase().includes(needle));
}

// The last-used workspace: a local preference holding the workspace id
// only (no name, no list), read back only when that id is in the server's
// list. It orders the rows and never skips the screen.
const LAST_USED_KEY = 'bc.lastWorkspaceId';
const ID_PATTERN = /^[A-Za-z0-9_-]{1,64}$/;

export function readLastWorkspaceId(): string | null {
    try {
        const value = window.localStorage.getItem(LAST_USED_KEY);
        return value && ID_PATTERN.test(value) ? value : null;
    } catch {
        return null;
    }
}

export function rememberWorkspace(id: string | null | undefined): void {
    if (!id || !ID_PATTERN.test(id)) return;
    try {
        window.localStorage.setItem(LAST_USED_KEY, id);
    } catch {
        // storage blocked (private window): the order just isn't remembered
    }
}
