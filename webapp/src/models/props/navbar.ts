export interface INavbarItem {
    key: string;
    name: string;
    url: string;
    icon?: React.ReactNode;
}

export interface IDrawerProps {
    drawerWidth?: number;
    mobileOpen?: boolean;
    handleDrawerToggle: () => void;
}
