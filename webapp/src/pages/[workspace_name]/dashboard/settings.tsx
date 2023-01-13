import React, { useEffect, useRef, useState } from 'react';

import { useDispatch } from 'react-redux';

import SettingsPrivacy from '@app/components/settings/workspace/settings-privacy';
import SettingsProfile from '@app/components/settings/workspace/settings-profile';
import { WorkspaceDangerZoneSettings } from '@app/components/settings/workspace/workspace-danger-zone-settings';
import { WorkspaceInformationSettings } from '@app/components/settings/workspace/workspace-information-settings';
import Layout from '@app/components/sidebar/layout';
import ParamTab, { TabPanel } from '@app/components/ui/param-tab';
import { getAuthUserPropsWithWorkspace } from '@app/lib/serverSideProps';
import { useAppSelector } from '@app/store/hooks';
import { useLazyGetWorkspaceQuery, usePatchExistingWorkspaceMutation } from '@app/store/workspaces/api';

//TODO: this will be a container for form settings
export default function MySettings(props: any) {
    // const { bannerImage, customDomain, description, id, profileImage, title, workspaceName } = props.workspace;
    // const imageRef = useRef<any>();

    // const [patchExistingWorkspace, { isLoading }] = usePatchExistingWorkspaceMutation();

    // const [trigger] = useLazyGetWorkspaceQuery();
    // const existingWorkspace = useAppSelector((state) => state.workspace);

    // const dispatch = useDispatch();
    // const [workspaceForm, setWorkspaceForm] = useState({
    //     title: '',
    //     custom_domain: '',
    //     workspace_name: '',
    //     description: '',
    //     profile_image: null,
    //     banner_image: null
    // });

    // useEffect(() => {
    //     setWorkspaceForm({
    //         title: title,
    //         workspace_name: workspaceName,
    //         description: description,
    //         profile_image: profileImage,
    //         banner_image: bannerImage,
    //         custom_domain: !!customDomain ? customDomain : ''
    //     });
    // }, []);

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

    // return (
    //     <Layout>
    //         <Header />
    //         <WorkspaceInformationSettings />
    //         <WorkspaceDangerZoneSettings />
    //     </Layout>
    // );

    const paramTabs = [
        {
            title: 'Profile',
            path: 'settings-profile'
        },
        {
            title: 'Privacy',
            path: 'settings-privacy'
        },
        {
            title: 'Advanced',
            path: 'settings-advanced'
        }
    ];

    return (
        <Layout>
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
        </Layout>
    );
}

export async function getServerSideProps(_context: any) {
    return await getAuthUserPropsWithWorkspace(_context);
}
