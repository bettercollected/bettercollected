import React from 'react';

import { AdminPanelSettings, PrivacyTip, Settings } from '@mui/icons-material';

import SettingsPrivacy from '@app/components/settings/workspace/settings-privacy';
import SettingsProfile from '@app/components/settings/workspace/settings-profile';
import { WorkspaceDangerZoneSettings } from '@app/components/settings/workspace/workspace-danger-zone-settings';
import SidebarLayout from '@app/components/sidebar/sidebar-layout';
import ParamTab, { TabPanel } from '@app/components/ui/param-tab';
import { getAuthUserPropsWithWorkspace } from '@app/lib/serverSideProps';

//TODO: this will be a container for form settings
export default function MySettings(props: any) {
    const Header = () => {
        return (
            <div className="w-full flex justify-between items-center pb-4 border-b-gray-200 mb-4 border-b-[1px]">
                <div>
                    <h1 className="font-semibold text-2xl">Settings</h1>
                    <p className="text-gray-600"> Manage your workspace settings and preferences.</p>
                </div>
            </div>
        );
    };

    const paramTabs = [
        {
            icon: <AdminPanelSettings />,
            title: 'Profile',
            path: 'settings-profile'
        },
        {
            icon: <PrivacyTip />,
            title: 'Privacy',
            path: 'settings-privacy'
        },
        {
            icon: <Settings />,
            title: 'Advanced',
            path: 'settings-advanced'
        }
    ];

    return (
        <SidebarLayout>
            <Header />
            <ParamTab tabMenu={paramTabs}>
                <TabPanel className="focus:outline-none" key="settings-profile">
                    <SettingsProfile />
                </TabPanel>
                <TabPanel className="focus:outline-none" key="settings-privacy">
                    <SettingsPrivacy />
                </TabPanel>
                <TabPanel className="focus:outline-none" key="mySubmissions">
                    <WorkspaceDangerZoneSettings />
                </TabPanel>
            </ParamTab>
        </SidebarLayout>
    );
}

export { getAuthUserPropsWithWorkspace as getServerSideProps } from '@app/lib/serverSideProps';
