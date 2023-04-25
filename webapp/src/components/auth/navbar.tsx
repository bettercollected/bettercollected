import React from 'react';

import { boolean } from 'property-information/lib/util/types';

import AuthAccountMenuDropdown from '@app/components/auth/account-menu-dropdown';
import { DRAWER_VIEW, useDrawer } from '@app/components/drawer-views/context';
import Button from '@app/components/ui/button';
import Hamburger from '@app/components/ui/hamburger';
import Logo from '@app/components/ui/logo';
import { Header } from '@app/layouts/_layout';
import { useBreakpoint } from '@app/lib/hooks/use-breakpoint';

interface IAuthNavbarProps {
    showHamburgerIcon?: boolean;
    showPlans?: boolean;
    mobileOpen?: boolean;
    handleDrawerToggle?: () => void;
    drawerView?: DRAWER_VIEW;
}

AuthNavbar.defaultProps = {
    showPlans: true,
    showHamburgerIcon: true,
    isMobileView: false,
    handleDrawerToggle: () => {}
};
export default function AuthNavbar({ showHamburgerIcon, showPlans, mobileOpen, handleDrawerToggle, drawerView = 'DASHBOARD_SIDEBAR' }: IAuthNavbarProps) {
    const { openDrawer, isOpen } = useDrawer();

    const handleOpenSidebar = () => {
        openDrawer(drawerView);
    };

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

    return (
        <>
            <Header className="!z-[1300]">
                <div className="flex flex-row w-full h-full py-2 md:py-0 justify-between items-center">
                    <div className="flex">
                        {!isMobileView() && showHamburgerIcon && <Hamburger isOpen={mobileOpen} className="!shadow-none mr-2 !bg-white hover:!bg-transparent !text-black-900 !flex !justify-start" onClick={handleDrawerToggle} />}
                        <Logo />
                    </div>
                    <div className="flex items-center justify-center gap-7">
                        {showPlans && (
                            <Button size="small" disabled>
                                View Plans
                            </Button>
                        )}
                        <AuthAccountMenuDropdown />
                    </div>
                </div>
            </Header>
        </>
    );
}
