import React from 'react';

import cn from 'classnames';

import Button from '@app/components/ui/button/button';
import { Header } from '@app/layouts/_layout';
import { useBreakpoint } from '@app/lib/hooks/use-breakpoint';
import useDimension from '@app/lib/hooks/use-dimension';

import { useDrawer } from '../drawer-views/context';
import { PlusCircle } from '../icons/plus-circle';
import { useModal } from '../modal-views/context';
import Hamburger from '../ui/hamburger';
import Logo from '../ui/logo';
import SidebarExpandable from './_expandable';

export default function Layout(props: any) {
    const children = props.children;
    const isNavbarRequired = props.children;
    const { openModal } = useModal();
    const { openDrawer, isOpen } = useDrawer();

    const screenSize = useBreakpoint();

    const handleOpenSidebar = () => {
        openDrawer('DASHBOARD_SIDEBAR');
    };

    const checkIfSideBarRender = () => {
        switch (screenSize) {
            case 'xs':
                return false;
            case 'sm':
                return false;
            case 'md':
                return false;
            case 'lg':
                return false;
            case 'xl':
                return true;
            case '2xl':
                return true;
            case '3xl':
                return true;
            case '4xl':
                return true;
        }
    };

    return (
        <div className="ltr:xl:pl-24 rtl:xl:pr-24 ltr:2xl:pl-28 rtl:2xl:pr-28">
            {isNavbarRequired && (
                <Header>
                    <>
                        <div className="flex flex-row w-full h-full py-2 md:py-0 justify-between items-center">
                            <div className={'flex'}>
                                {!checkIfSideBarRender() && <Hamburger isOpen={isOpen} className="!shadow-none !bg-white !text-black" onClick={handleOpenSidebar} />}
                                <Logo />
                            </div>
                        </div>
                    </>
                </Header>
            )}
            {checkIfSideBarRender() && <SidebarExpandable />}
            <main className={cn('px-4 xl:left-24 right-0 w-full xl:w-auto absolute top-24 pt-4 pb-16 sm:px-6 sm:pb-20 lg:px-8 xl:pb-24 3xl:px-10 3xl:pt-2.5')}>{children}</main>
        </div>
    );
}
