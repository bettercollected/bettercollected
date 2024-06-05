export interface INavbarItem {
    key: string;
    name: React.ReactNode;
    url: string;
    icon?: React.ReactNode;
    onClick?: () => void;
}

export interface IDrawerProps {
    drawerWidth?: number;
    mobileOpen?: boolean;
    className?: string;
    handleDrawerToggle: () => void;
    topNavList: Array<any>;
    bottomNavList: Array<any>;
}
