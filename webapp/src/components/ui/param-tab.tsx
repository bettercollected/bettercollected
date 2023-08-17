import React, { useEffect, useMemo, useRef, useState } from 'react';

import { useRouter } from 'next/router';

import { Tab, TabItem, TabPanel, TabPanels } from '@app/components/ui/tab';
import { useBreakpoint } from '@app/lib/hooks/use-breakpoint';
import { useClickAway } from '@app/lib/hooks/use-click-away';
import { authApi } from '@app/store/auth/api';
import { useAppSelector } from '@app/store/hooks';

interface TabMenuItem {
    title: React.ReactNode;
    path: string;
    icon?: any;
}

interface ParamTabTypes {
    tabMenu: TabMenuItem[];
    children: React.ReactChild[];
    isRouteChangeable?: boolean;
    className?: string;
}

export { TabPanel };

export default function ParamTab({ tabMenu, children, isRouteChangeable = true, className = '' }: ParamTabTypes) {
    const router = useRouter();
    const dropdownEl = useRef<HTMLDivElement>(null);
    const [selectedTabIndex, setSelectedTabIndex] = useState(0);
    const [visibleMobileMenu, setVisibleMobileMenu] = useState(false);
    const statusQuerySelect = useMemo(() => authApi.endpoints.getStatus.select(), []);
    const selectGetStatus = useAppSelector(statusQuerySelect);
    const breakpoints = useBreakpoint();

    function handleTabChange(index: number) {
        if (isRouteChangeable) {
            const query = router.query;
            delete query.sub_id;
            router
                .push(
                    {
                        pathname: router.pathname,
                        query: { ...query, view: tabMenu[index].path }
                    },
                    undefined,
                    { scroll: true, shallow: true }
                )
                .then((r) => r)
                .catch((e) => e);
        } else {
            setSelectedTabIndex(index);
        }
    }

    useEffect(() => {
        if (router?.query?.view && isRouteChangeable) {
            setSelectedTabIndex(tabMenu.findIndex((item) => router.query.view === item.path));
        }
    }, [router.query, isRouteChangeable, tabMenu]);

    useEffect(() => {
        // Reset tab params to forms if logged out and tab param index is at submissions
        if (!!selectGetStatus.error) {
            setSelectedTabIndex(0);
            router
                .push(
                    {
                        pathname: router.pathname,
                        query: { ...router.query, view: tabMenu[0].path }
                    },
                    undefined,
                    { scroll: true, shallow: true }
                )
                .then((r) => r)
                .catch((e) => e);
        }
    }, [selectGetStatus]);

    useClickAway(dropdownEl, () => {
        setVisibleMobileMenu(false);
    });
    return (
        <Tab.Group selectedIndex={selectedTabIndex} onChange={(index: any) => handleTabChange(index)}>
            <div className={`flex flex-row justify-between py-[26px] ${className}`}>
                <Tab.List className="relative w-full text-sm gap-8">
                    <div className="flex gap-6 w-full border-b-[1px] top-[-2px] border-black-500 justify-between md:justify-start md:gap-8 xl:gap-10">
                        {tabMenu.map((item) => (
                            <TabItem key={item.path} className="p-0">
                                <div className="flex items-center">
                                    {item.icon && ['md', 'lg', 'xl', '2xl'].indexOf(breakpoints) === -1 && <span className="block">{item.icon}</span>}
                                    {['xs', '2xs', 'sm'].indexOf(breakpoints) === -1 && <div className="">{item.title}</div>}
                                </div>
                            </TabItem>
                        ))}
                    </div>
                </Tab.List>
            </div>
            <TabPanels>{children}</TabPanels>
        </Tab.Group>
    );
}
