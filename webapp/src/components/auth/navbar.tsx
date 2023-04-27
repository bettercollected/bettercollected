import React from 'react';

import AuthAccountMenuDropdown from '@app/components/auth/account-menu-dropdown';
import { DRAWER_VIEW } from '@app/components/drawer-views/context';
import ProPlanHoc from '@app/components/hoc/pro-plan-hoc';
import Button from '@app/components/ui/button';
import Hamburger from '@app/components/ui/hamburger';
import Logo from '@app/components/ui/logo';
import { useBreakpoint } from '@app/lib/hooks/use-breakpoint';
import { useIsMounted } from '@app/lib/hooks/use-is-mounted';
import { useWindowScroll } from '@app/lib/hooks/use-window-scroll';

interface IAuthNavbarProps {
    showHamburgerIcon?: boolean;
    checkMyDataEnabled?: boolean;
    showPlans?: boolean;
    mobileOpen?: boolean;
    handleDrawerToggle?: () => void;
    drawerView?: DRAWER_VIEW;
}

AuthNavbar.defaultProps = {
    showPlans: true,
    checkMyDataEnabled: false,
    showHamburgerIcon: true,
    isMobileView: false,
    handleDrawerToggle: () => {}
};

export function Header(props: any) {
    const windowScroll = useWindowScroll();
    const isMounted = useIsMounted();

    const propClassNames = props?.className ?? '';
    const navClassNames = isMounted && windowScroll.y > 10 ? 'bg-gradient-to-b from-white to-white/80 shadow-card backdrop-blur dark:from-dark dark:to-dark/80' : 'border-b-[0.5px] border-neutral-100 dark:border-neutral-700 bg-white dark:bg-dark';

    return <nav className={`fixed top-0 !z-30 flex w-full items-center justify-between px-5 lg:pr-10 transition-all duration-300 ltr:right-0 rtl:left-0 h-[68px] ${navClassNames} ${propClassNames}`}>{props.children}</nav>;
}

export default function AuthNavbar({ showHamburgerIcon, checkMyDataEnabled, showPlans, mobileOpen, handleDrawerToggle, drawerView = 'DASHBOARD_SIDEBAR' }: IAuthNavbarProps) {
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
        <Header className="!z-[1300]">
            <div className="flex flex-row w-full h-full py-2 md:py-0 justify-between items-center">
                <div className="flex">
                    {!isMobileView() && showHamburgerIcon && <Hamburger isOpen={mobileOpen} className="!shadow-none mr-2 !bg-white hover:!bg-white !text-black-900 !flex !justify-start" onClick={handleDrawerToggle} />}
                    <Logo />
                </div>
                <div className="flex items-center justify-center gap-7">
                    {showPlans && (
                        <ProPlanHoc hideChildrenIfPro={true}>
                            <Button size="small">Upgrade</Button>
                        </ProPlanHoc>
                    )}
                    <AuthAccountMenuDropdown checkMyDataEnabled={checkMyDataEnabled} />
                </div>
            </div>
        </Header>
    );
}
