import React, { useEffect, useMemo, useRef, useState } from 'react';

import Image from 'next/image';

import _ from 'lodash';

import cn from 'classnames';

import { Header } from '@app/layouts/_layout';
import { useBreakpoint } from '@app/lib/hooks/use-breakpoint';
import { authApi } from '@app/store/auth/api';
import { useAppSelector } from '@app/store/hooks';

import { useDrawer } from '../drawer-views/context';
import Hamburger from '../ui/hamburger';
import Logo from '../ui/logo';
import SidebarExpandable from './_expandable';

export default function SidebarLayout(props: any) {
    const children = props.children;
    const isNavbarRequired = props.children;
    const { openDrawer, isOpen } = useDrawer();
    const [anchorEl, setAnchorEl] = useState(null);

    const screenSize = useBreakpoint();

    const statusQuerySelect = useMemo(() => authApi.endpoints.getStatus.select('status'), []);
    const selectGetStatus = useAppSelector(statusQuerySelect);

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

    const user = selectGetStatus?.data?.user;

    const profileName = _.capitalize(user?.first_name) + ' ' + _.capitalize(user?.last_name);

    return (
        <div className="ltr:xl:pl-24 rtl:xl:pr-24 ltr:2xl:pl-28 rtl:2xl:pr-28">
            {isNavbarRequired && (
                <Header>
                    <>
                        <div className="flex flex-row w-full h-full py-2 md:py-0 justify-between items-center">
                            <div className={'flex'}>
                                {!checkIfSideBarRender() && <Hamburger isOpen={isOpen} className="!shadow-none !bg-white !text-black !flex !justify-start" onClick={handleOpenSidebar} />}
                                <Logo />
                            </div>
                            {['xs', 'sm'].indexOf(screenSize) === -1 && !!profileName[0] && (
                                <div className="flex items-center mt-2">
                                    <div className="flex rounded-full w-10 h-10 items-center justify-center mr-2 bg-blue-50">
                                        {user?.profile_image ? <Image src={user?.profile_image} className="rounded-full" width={64} height={64} /> : <>{profileName[0]?.toUpperCase()}</>}
                                    </div>
                                    <div className="italic font-bold text-md text-gray-600">{profileName.trim() || user?.email || ''}</div>
                                </div>
                            )}
                        </div>
                    </>
                </Header>
            )}
            {checkIfSideBarRender() && <SidebarExpandable />}
            <main className={cn('px-4 xl:left-24 right-0 w-full xl:w-auto absolute top-24 md:pt-4 sm:px-6 lg:px-8 3xl:px-10 3xl:pt-2.5')}>{children}</main>
        </div>
    );
}
