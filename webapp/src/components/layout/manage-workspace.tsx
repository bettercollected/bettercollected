import React from 'react';

import BreadcrumbsRenderer from '@app/components/form/renderer/breadcrumbs-renderer';
import SettingsDrawer from '@app/components/sidebar/settings-drawer';
import SidebarLayout from '@app/components/sidebar/sidebar-layout';
import { BreadcrumbsItem } from '@app/models/props/breadcrumbs-item';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';

export default function ManageWorkspaceLayout({ children }: any) {
    const workspace = useAppSelector(selectWorkspace);

    const breadcrumbsItem: Array<BreadcrumbsItem> = [
        {
            title: 'Dashboard',
            url: `/${workspace?.workspaceName}/dashboard`
        },
        {
            title: 'Manage Workspace',
            disabled: true
        }
    ];

    return (
        <SidebarLayout DrawerComponent={SettingsDrawer}>
            <div className="relative">
                <div className=" flex pt-5 items-center space-x-4">
                    <BreadcrumbsRenderer items={breadcrumbsItem} />
                </div>
                <div className=" pt-10 sh1">Manage Workspace</div>
                <div className="absolute lg:left-[-40px] px-5 lg:px-10 pb-10 mt-24 top-0 w-full xl:max-w-289-calc-289">{children}</div>
            </div>
        </SidebarLayout>
    );
}
