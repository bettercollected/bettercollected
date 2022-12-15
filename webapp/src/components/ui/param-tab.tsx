import React, { useEffect, useRef, useState } from 'react';

import { useRouter } from 'next/router';

import styled from '@emotion/styled';
import cn from 'classnames';

import { ChevronDown } from '@app/components/icons/chevron-down';
import { Tab, TabItem, TabPanel, TabPanels } from '@app/components/ui/tab';
import { useBreakpoint } from '@app/lib/hooks/use-breakpoint';
import { useClickAway } from '@app/lib/hooks/use-click-away';
import { useIsMounted } from '@app/lib/hooks/use-is-mounted';

interface TabMenuItem {
    title: React.ReactNode;
    path: string;
    icon?: any;
}

interface ParamTabTypes {
    tabMenu: TabMenuItem[];
    children: React.ReactChild[];
    isRouteChangeable?: boolean;
}

export { TabPanel };

export default function ParamTab({ tabMenu, children, isRouteChangeable = true }: ParamTabTypes) {
    const router = useRouter();
    const isMounted = useIsMounted();
    const breakpoint = useBreakpoint();
    const dropdownEl = useRef<HTMLDivElement>(null);
    const [selectedTabIndex, setSelectedTabIndex] = useState(0);
    const [visibleMobileMenu, setVisibleMobileMenu] = useState(false);
    function handleTabChange(index: number) {
        if (isRouteChangeable) {
            router
                .push(
                    {
                        pathname: router.pathname,
                        query: { ...router.query, view: tabMenu[index].path }
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
        // else {
        //     setSelectedTabIndex(0);
        // }
    }, [router.query, isRouteChangeable, tabMenu]);

    useClickAway(dropdownEl, () => {
        setVisibleMobileMenu(false);
    });
    return (
        <Tab.Group selectedIndex={selectedTabIndex} onChange={(index: any) => handleTabChange(index)}>
            <div className="flex flex-row justify-between">
                <Tab.List className="relative w-full mb-6 text-sm before:absolute before:left-0 before:bottom-0 before:rounded-sm before:bg-gray-200 dark:bg-dark dark:before:bg-gray-800 gap-8 rounded-none md:before:h-0.5">
                    {/* {isMounted && ['xs', 'sm'].indexOf(breakpoint) !== -1 ? (
                        <div ref={dropdownEl} className="rounded-lg w-full border-2 border-gray-200 dark:border-gray-700">
                            <button type="button" onClick={() => setVisibleMobileMenu(!visibleMobileMenu)} className="flex w-full items-center justify-between py-2.5 px-4 uppercase text-gray-400 dark:text-gray-300 sm:px-5 sm:py-3.5">
                                <span className="font-medium text-gray-900 dark:text-gray-100">{tabMenu[selectedTabIndex].title}</span>
                                <ChevronDown className="h-auto w-3.5" />
                            </button>
                            <div
                                className={cn(
                                    'absolute top-full left-0 z-10 mt-1 grid w-full gap-0.5 rounded-lg border border-gray-200 bg-white p-2 text-left shadow-large dark:border-gray-700 dark:bg-gray-800 xs:gap-1',
                                    visibleMobileMenu ? 'visible opacity-100' : 'invisible opacity-0'
                                )}
                            >
                                {tabMenu.map((item) => (
                                    <div key={item.path} onClick={() => setVisibleMobileMenu(false)} className="w-full">
                                        <TabItem className="w-full">{item.title}</TabItem>
                                    </div>
                                ))}
                            </div>
                        </div>
                    ) : ( */}
                    <div className="flex gap-6 w-full justify-between md:justify-start md:gap-8 xl:gap-10 3xl:gap-12">
                        {tabMenu.map((item) => (
                            <TabItem key={item.path}>
                                <div className="flex items-center">
                                    {item.icon && <span className="pr-2">{item.icon}</span>}
                                    {item.title}
                                </div>
                            </TabItem>
                        ))}
                    </div>
                    {/* )} */}
                </Tab.List>
            </div>
            <TabPanels>{children}</TabPanels>
        </Tab.Group>
    );
}
