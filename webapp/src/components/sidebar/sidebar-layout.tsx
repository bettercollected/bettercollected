import React from 'react';

import { Box } from '@mui/material';
import cn from 'classnames';

import AuthNavbar from '@app/components/auth/navbar';
import DashboardDrawer from '@app/components/sidebar/dashboard-drawer';

interface ISidebarLayout {
    children: any;
    DrawerComponent?: any;
}

export default function SidebarLayout({ children, DrawerComponent = DashboardDrawer }: ISidebarLayout) {
    const drawerWidth = 289;

    const [mobileOpen, setMobileOpen] = React.useState(false);
    const handleDrawerToggle = () => {
        setMobileOpen(!mobileOpen);
    };

    return (
        <div className="relative min-h-screen w-full">
            <AuthNavbar handleDrawerToggle={handleDrawerToggle} mobileOpen={mobileOpen} />
            <DrawerComponent drawerWidth={drawerWidth} mobileOpen={mobileOpen} handleDrawerToggle={handleDrawerToggle} />
            <Box className={`float-none lg:float-right mt-[68px] min-h-calc-68 px-5 lg:px-10 ${DrawerComponent === DashboardDrawer ? 'py-6' : ''}`} component="main" sx={{ display: 'flex', width: { lg: `calc(100% - ${drawerWidth}px)` } }}>
                <div className={cn('w-full h-full')}>{children}</div>
            </Box>
        </div>
    );
}
