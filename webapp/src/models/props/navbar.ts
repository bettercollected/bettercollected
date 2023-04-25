export interface INavbarItem {
    key: string;
    name: string;
    url: string;
    icon?: any;
}

export interface IDrawerProps {
    drawerWidth?: number;
    mobileOpen?: boolean;
    handleDrawerToggle: () => void;
}
