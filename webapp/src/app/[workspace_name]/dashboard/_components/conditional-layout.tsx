"use client";

import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';
import SidebarLayoutApp from '@Components/sidebar/SidebarLayoutApp';
import { usePathname } from 'next/navigation';
import React from 'react';



const ConditionalLayout: React.FC<{ children: React.ReactNode }> = ({ children }) => {

    const pathname = usePathname();

    const workspace = useAppSelector(selectWorkspace);

    const showSidebar = pathname === `/${workspace?.workspaceName}/dashboard/forms`
        || pathname === `/${workspace?.workspaceName}/dashboard/overview`
        || pathname === `/${workspace?.workspaceName}/dashboard/responders-groups`
        || pathname === `/${workspace?.workspaceName}/dashboard/settings`
        || pathname === `/${workspace?.workspaceName}/dashboard/members`
        || pathname === `/${workspace?.workspaceName}/dashboard/custom-domain`
        || pathname === `/${workspace?.workspaceName}/dashboard/deletion-requests`
        || pathname === `/${workspace?.workspaceName}/dashboard/account-settings`

    if (!showSidebar) {
        return <>{children}</>;
    }
    return (<SidebarLayoutApp boxClassName="px-5 lg:px-10 pt-10">
        {children}
    </SidebarLayoutApp>)

};

export default ConditionalLayout;