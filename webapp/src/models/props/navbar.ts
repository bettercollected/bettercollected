export interface INavbarItem {
    key: string;
    name: React.ReactNode;
    url: string;
    icon?: React.ReactNode;
    onClick?: () => void;
    /** Highlight only on an exact pathname match — for items whose URL is a
     *  prefix of every other route (e.g. the dashboard root). */
    exactMatch?: boolean;
    /** Only rendered for workspace admins. */
    adminOnly?: boolean;
    /** Overrides URL-based matching — for items whose active state isn't a
     *  route (e.g. Site settings, which is a view on the dashboard root). */
    isActive?: boolean;
}

export interface INavGroup {
    /** Quiet uppercase section label; groups nav by meaning, not permission. */
    label: string;
    items: Array<INavbarItem>;
}

export interface IDrawerProps {
    drawerWidth?: number;
    mobileOpen?: boolean;
    className?: string;
    handleDrawerToggle: () => void;
    navGroups: Array<INavGroup>;
}
