"use client";
import React, { ReactNode, useEffect, useMemo, useState } from 'react';

import { useRouter, usePathname, useSearchParams } from 'next/navigation';

import { Tab, TabItem, TabPanel, TabPanels } from '@app/Components/ui/tab';
import { authApi } from '@app/store/auth/api';
import { useAppSelector } from '@app/store/hooks';

interface TabMenuItem {
    title: React.ReactNode;
    path: string;
    icon?: any;
}

interface ParamTabTypes {
    tabMenu: TabMenuItem[];
    children: ReactNode;
    isRouteChangeable?: boolean;
    className?: string;
    showInfo?: boolean;
    initialIndex?: number;
}

export { TabPanel };

export default function ParamTab({ tabMenu, children, isRouteChangeable = true, className = '', showInfo = false, initialIndex }: ParamTabTypes) {
    const router = useRouter();
    const pathname = usePathname();
    const searchParams = useSearchParams();

    const [selectedTabIndex, setSelectedTabIndex] = useState(() => {
        if (initialIndex !== undefined) return initialIndex;
        const view = searchParams?.get('view');
        const index = tabMenu.findIndex((item) => view === item.path);
        return index === -1 ? 0 : index;
    });
    const statusQuerySelect = useMemo(() => authApi.endpoints.getStatus.select(), []);
    const selectGetStatus = useAppSelector(statusQuerySelect);

    function handleTabChange(index: number) {
        if (isRouteChangeable) {
            const params = new URLSearchParams(searchParams?.toString());
            params.delete('sub_id');
            params.set('view', tabMenu[index].path);
            router.push(`${pathname}?${params.toString()}`, { scroll: false });
        } else {
            setSelectedTabIndex(index);
        }
    }

    useEffect(() => {
        const view = searchParams?.get('view');
        if (view && isRouteChangeable) {
            setSelectedTabIndex(tabMenu.findIndex((item) => view === item.path));
        }
    }, [searchParams, isRouteChangeable, tabMenu]);

    useEffect(() => {
        // Reset tab params to forms if logged out and tab param index is at submissions
        if (!!selectGetStatus.error && selectedTabIndex === 2) {
            setSelectedTabIndex(0);
            const params = new URLSearchParams(searchParams?.toString());
            params.set('view', tabMenu[0].path);
            router.push(`${pathname}?${params.toString()}`, { scroll: true });
        }
    }, [selectGetStatus, selectedTabIndex, pathname, searchParams, tabMenu, router]);

    return (
        <Tab.Group selectedIndex={selectedTabIndex} onChange={(index: any) => handleTabChange(index)}>
            <div className={`flex flex-row justify-between py-[26px] ${className}`}>
                <Tab.List className="relative w-full gap-8  text-sm">
                    <div className="border-black-300 flex max-w-full justify-between gap-5 overflow-x-auto border-b-[1px] pb-[24px]">
                        <div className="top-[-2px] flex w-full justify-start gap-2 px-4 xl:gap-3">
                            {tabMenu.map((item, index) => (
                                <TabItem key={item.path} className={`min-w-fit ${selectedTabIndex !== index ? 'hover:bg-black-100' : ''}`}>
                                    <div className={`flex items-center ${selectedTabIndex === index ? 'text-black-900' : 'text-black-600'}`}>
                                        <div className="p1">{item.title}</div>
                                    </div>
                                </TabItem>
                            ))}
                        </div>
                    </div>
                </Tab.List>
            </div>
            <TabPanels>{children}</TabPanels>
        </Tab.Group>
    );
}
