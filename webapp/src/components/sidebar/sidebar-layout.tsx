import React from 'react';

import { Box } from '@mui/material';
import cn from 'classnames';
import { AnimatePresence, motion } from 'framer-motion';

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
        <AnimatePresence mode="wait" initial={true} onExitComplete={() => window.scrollTo(0, 0)}>
            <div className="relative min-h-screen w-full">
                <AuthNavbar handleDrawerToggle={handleDrawerToggle} mobileOpen={mobileOpen} />
                <DrawerComponent drawerWidth={drawerWidth} mobileOpen={mobileOpen} handleDrawerToggle={handleDrawerToggle} />
                <Box className={`float-none lg:float-right mt-[68px] min-h-calc-68 px-5 lg:px-10`} component="main" sx={{ display: 'flex', width: { lg: `calc(100% - ${drawerWidth}px)` } }}>
                    <motion.div
                        initial={{ x: 0, opacity: 0 }}
                        animate={{ x: 0, opacity: 1 }}
                        exit={{ x: 300, opacity: 0 }}
                        transition={{
                            ease: 'linear',
                            duration: 0.5,
                            x: { duration: 0.5 }
                        }}
                        className={cn('w-full h-full')}
                    >
                        {children}
                    </motion.div>
                </Box>
            </div>
        </AnimatePresence>
    );
}
