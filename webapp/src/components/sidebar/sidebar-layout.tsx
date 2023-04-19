import React from 'react';

import cn from 'classnames';

import AuthAccountMenuDropdown from '@app/components/auth/account-menu-dropdown';
import { useDrawer } from '@app/components/drawer-views/context';
import SidebarExpandable from '@app/components/sidebar/_expandable';
import Hamburger from '@app/components/ui/hamburger';
import Logo from '@app/components/ui/logo';
import { Header } from '@app/layouts/_layout';
import { useBreakpoint } from '@app/lib/hooks/use-breakpoint';

import Button from '../ui/button/button';

export default function SidebarLayout(props: any) {
    const children = props.children;
    const isNavbarRequired = props.children;
    const { openDrawer, isOpen } = useDrawer();

    const screenSize = useBreakpoint();

    const handleOpenSidebar = () => {
        openDrawer('DASHBOARD_SIDEBAR');
    };

    const checkIfSideBarRender = () => {
        switch (screenSize) {
            case 'xs':
            case 'sm':
            case 'md':
            case 'lg':
                return false;
            default:
                return true;
        }
    };

    return (
        <div className="ltr:xl:pl-24 rtl:xl:pr-24 ltr:2xl:pl-28 rtl:2xl:pr-28">
            {isNavbarRequired && (
                <Header>
                    <div className="flex flex-row w-full h-full py-2 md:py-0 justify-between items-center">
                        <div className="flex">
                            {!checkIfSideBarRender() && <Hamburger isOpen={isOpen} className="!shadow-none !bg-white !text-black-900 !flex !justify-start" onClick={handleOpenSidebar} />}
                            <Logo />
                        </div>
                        <div className="flex items-center justify-center gap-7">
                            <Button size="small" disabled>
                                View Plans
                            </Button>
                            <AuthAccountMenuDropdown />
                        </div>
                    </div>
                </Header>
            )}
            {checkIfSideBarRender() && <SidebarExpandable />}
            <main className={cn('px-4 xl:left-24 right-0 w-full xl:w-auto absolute top-[68px] md:pt-4 sm:px-6 lg:px-8 3xl:px-10 3xl:pt-2.5')}>{children}</main>
        </div>
    );
}
