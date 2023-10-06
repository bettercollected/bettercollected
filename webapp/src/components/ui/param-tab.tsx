import React, { ReactNode, useEffect, useMemo, useState } from 'react';

import { useRouter } from 'next/router';

import { Tab, TabItem, TabPanel, TabPanels } from '@app/components/ui/tab';
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
}

export { TabPanel };

export default function ParamTab({ tabMenu, children, isRouteChangeable = true, className = '', showInfo = false }: ParamTabTypes) {
    const router = useRouter();
    const [selectedTabIndex, setSelectedTabIndex] = useState(tabMenu.findIndex((item) => router.query.view === item.path));
    const statusQuerySelect = useMemo(() => authApi.endpoints.getStatus.select(), []);
    const selectGetStatus = useAppSelector(statusQuerySelect);

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
                    { scroll: false, shallow: false }
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
    }, [router.query]);

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

    return (
        <Tab.Group selectedIndex={selectedTabIndex} onChange={(index: any) => handleTabChange(index)}>
            <div className={`flex flex-row justify-between py-[26px] ${className}`}>
                <Tab.List className="relative w-full text-sm gap-8">
                    <div className="flex justify-between pb-[24px] border-b-[1px] border-black-300 max-w-full gap-5 overflow-x-auto">
                        <div className="flex sm:gap-3 top-[-2px] justify-start xl:gap:6">
                            {tabMenu.map((item) => (
                                <TabItem key={item.path} className="min-w-fit">
                                    <div className="flex items-center">
                                        <div className="">{item.title}</div>
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
