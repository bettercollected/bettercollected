import React from 'react';

import AuthAccountMenuDropdown from '@app/components/auth/account-menu-dropdown';
import { useDrawer } from '@app/components/drawer-views/context';
import Button from '@app/components/ui/button';
import Hamburger from '@app/components/ui/hamburger';
import Logo from '@app/components/ui/logo';
import { Header } from '@app/layouts/_layout';
import { useBreakpoint } from '@app/lib/hooks/use-breakpoint';

interface IAuthNavbarProps {
    showHamburgerIcon: boolean;
    showPlans?: boolean;
}

AuthNavbar.defaultProps = {
    showPlans: true
};
export default function AuthNavbar({ showHamburgerIcon, showPlans }: IAuthNavbarProps) {
    const { openDrawer, isOpen } = useDrawer();

    const handleOpenSidebar = () => {
        openDrawer('DASHBOARD_SIDEBAR');
    };

    return (
        <Header>
            <div className="flex flex-row w-full h-full py-2 md:py-0 justify-between items-center">
                <div className="flex mr-2">
                    {showHamburgerIcon && <Hamburger isOpen={isOpen} className="!shadow-none !bg-white !text-black-900 !flex !justify-start" onClick={handleOpenSidebar} />}
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
    );
}
