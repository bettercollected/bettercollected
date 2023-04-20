import React from 'react';

import { Box } from '@mui/material';
import cn from 'classnames';

import AuthAccountMenuDropdown from '@app/components/auth/account-menu-dropdown';
import MuiDrawer from '@app/components/sidebar/mui-drawer';
import Hamburger from '@app/components/ui/hamburger';
import Logo from '@app/components/ui/logo';
import { Header } from '@app/layouts/_layout';
import { useBreakpoint } from '@app/lib/hooks/use-breakpoint';

export default function SidebarLayout(props: any) {
    const drawerWidth = 289;
    const children = props.children;
    const isNavbarRequired = props.children;

    const screenSize = useBreakpoint();

    const isMobileView = () => {
        switch (screenSize) {
            case 'xs':
            case '2xs':
            case 'sm':
            case 'md':
                return false;
            default:
                return true;
        }
    };

    const [mobileOpen, setMobileOpen] = React.useState(false);

    const handleDrawerToggle = () => {
        setMobileOpen(!mobileOpen);
    };

    return (
        <div className="relative min-h-screen w-full">
            {isNavbarRequired && (
                <Header className="!z-[1300]">
                    <div className="flex flex-row w-full h-full py-2 md:py-0 justify-between items-center">
                        <div className="flex">
                            {!isMobileView() && <Hamburger isOpen={mobileOpen} className="!shadow-none mr-2 !bg-white hover:!bg-transparent !text-black-900 !flex !justify-start" onClick={handleDrawerToggle} />}
                            <Logo />
                        </div>
                        <div className="flex items-center justify-center gap-7">
                            {/* <Button size="small" disabled>
                                View Plans
                            </Button> */}
                            <AuthAccountMenuDropdown />
                        </div>
                    </div>
                </Header>
            )}

            <MuiDrawer drawerWidth={drawerWidth} mobileOpen={mobileOpen} handleDrawerToggle={handleDrawerToggle} />
            <Box className="float-none lg:float-right mt-[68px] px-5 py-6 lg:px-10" component="main" sx={{ display: 'flex', width: { lg: `calc(100% - ${drawerWidth}px)` } }}>
                <main className={cn('w-full')}>{children}</main>
            </Box>
        </div>
    );
}
