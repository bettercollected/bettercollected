// The name to show for a workspace. A workspace without a title has an
// auto-generated handle (`workspaceName`): its owner's id, or a new object id.
// That is an identifier, not a name; it stays in URLs and API calls but is
// never shown as text.

const OBJECT_ID = /^[0-9a-f]{24}$/i;
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

interface NamedWorkspace {
    title?: string | null;
    workspaceName?: string | null;
    id?: string | null;
    ownerId?: string | null;
}

/** An auto-generated id (an object id or a UUID), or one of the workspace's own ids. */
export function looksLikeId(value: string, ...knownIds: Array<string | null | undefined>): boolean {
    return OBJECT_ID.test(value) || UUID.test(value) || knownIds.includes(value);
}

/**
 * The workspace's title, else its handle when that is a readable one, else
 * `undefined` so the caller shows its own translated fallback. Never an id.
 */
export function workspaceDisplayName(workspace?: NamedWorkspace | null): string | undefined {
    const title = workspace?.title?.trim();
    if (title) return title;
    const handle = workspace?.workspaceName?.trim();
    if (handle && !looksLikeId(handle, workspace?.id, workspace?.ownerId)) return handle;
    return undefined;
}
