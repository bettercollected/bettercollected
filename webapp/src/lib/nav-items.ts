import { WorkspacePermission } from '@app/models/enums/workspace-permission';
import { INavbarItem } from '@app/models/props/navbar';

const trimSlash = (path: string) => (path.length > 1 ? path.replace(/\/+$/, '') : path);

const isUnder = (pathname: string, root: string) => pathname === root || pathname.startsWith(root + '/');

/**
 * Is this sidebar item the current one? A prefix match, so nested routes
 * (/members/collaborators, /ai/memory) keep their item selected; items whose
 * URL prefixes everything (the dashboard root) opt into an exact match, and
 * items whose active state isn't a route pass it in directly.
 */
export function isNavItemActive(pathname: string | null | undefined, item: INavbarItem): boolean {
    if (item.isActive !== undefined) return item.isActive;
    if (!pathname) return false;
    const path = trimSlash(pathname);
    const root = item.activePath ?? item.url;
    return item.exactMatch ? path === root : isUnder(path, root);
}

/**
 * The item that titles the page: the longest matching path wins, since the
 * Site item's URL (the dashboard root) is a prefix of every other route.
 */
export function navItemForPath(pathname: string | null | undefined, items: Array<INavbarItem>): INavbarItem | undefined {
    if (!pathname) return undefined;
    const path = trimSlash(pathname);
    const rootOf = (item: INavbarItem) => item.activePath ?? item.url;
    return items.filter((item) => isUnder(path, rootOf(item))).sort((a, b) => rootOf(b).length - rootOf(a).length)[0];
}

/** The items this member may see: an item names the permission it needs. */
export function visibleNavItems(items: Array<INavbarItem>, can: (permission: WorkspacePermission) => boolean): Array<INavbarItem> {
    return items.filter((item) => (!item.permission || can(item.permission)) && (!item.anyPermission || item.anyPermission.some((permission) => can(permission))));
}
