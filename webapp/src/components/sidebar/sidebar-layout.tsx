import React from 'react';

import {Box} from '@mui/material';
import cn from 'classnames';
import {AnimatePresence, motion} from 'framer-motion';

import AuthAccountMenuDropdown from '@app/components/auth/account-menu-dropdown';
import AuthNavbar from '@app/components/auth/navbar';
import DashboardDrawer from '@app/components/sidebar/dashboard-drawer';

interface ISidebarLayout {
    children: any;
    DrawerComponent?: any;
    boxClassName?: string;
}

export default function SidebarLayout({
                                          children,
                                          DrawerComponent = DashboardDrawer,
                                          boxClassName = ''
                                      }: ISidebarLayout) {
    const drawerWidth = 289;

    const [mobileOpen, setMobileOpen] = React.useState(false);
    const handleDrawerToggle = () => {
        setMobileOpen(!mobileOpen);
    };

    return (
        <AnimatePresence mode="wait" initial={true} onExitComplete={() => window.scrollTo(0, 0)}>
            <div className="relative min-h-screen w-full">
                <div className="lg:hidden">
                    <AuthNavbar handleDrawerToggle={handleDrawerToggle} mobileOpen={mobileOpen}/>
                </div>
                <DrawerComponent drawerWidth={drawerWidth} mobileOpen={mobileOpen}
                                 handleDrawerToggle={handleDrawerToggle}/>
                <Box
                    className={`float-none lg:float-right lg:min-h-screen bg-black-100 min-h-calc-68 mt-[68px] lg:mt-0`}
                    component="main" sx={{display: 'flex', width: {lg: `calc(100% - ${drawerWidth}px)`}}}>

                    <div className="flex flex-col w-full">
                        <div
                            className="flex w-full py-3 z-[1000] sticky top-[68px] lg:top-0 bg-white justify-between px-5 lg:px-10 items-center">
                            <span className="h3-new">My Workspace</span>
                            <div className="hidden lg:flex">
                                <AuthAccountMenuDropdown hideMenu={false} isClientDomain={false}/>
                            </div>
                        </div>
                        <motion.div
                            initial={{x: 0, opacity: 0}}
                            animate={{x: 0, opacity: 1}}
                            exit={{x: 300, opacity: 0}}
                            transition={{
                                ease: 'linear',
                                duration: 0.5,
                                x: {duration: 0.5}
                            }}
                            className={cn(`w-full h-full`)}
                        >
                            <div className={cn("w-full h-full bg-black-100", boxClassName)}>
                                {children}
                            </div>
                        </motion.div>
                    </div>
                </Box>
            </div>
        </AnimatePresence>
    );
}
