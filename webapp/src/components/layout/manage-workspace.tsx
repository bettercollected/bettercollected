import React from 'react';

import MuiDrawer from '@app/components/sidebar/mui-drawer';
import SettingsDrawer from '@app/components/sidebar/settings-drawer';
import SidebarLayout from '@app/components/sidebar/sidebar-layout';

export default function ManageWorkspaceLayout({ children }: any) {
    return (
        <SidebarLayout DrawerComponent={SettingsDrawer}>
            <div className="relative">
                <div className="absolute lg:left-[-40px] px-5 lg:px-10 pb-10 top-0 w-full xl:max-w-289-calc-289">{children}</div>

                {/*<MuiDrawer drawer={<></>} anchor="right" handleDrawerToggle={() => {*/}
                {/*}}/>*/}
            </div>
        </SidebarLayout>
    );
}
