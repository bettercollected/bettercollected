import React from 'react';

import { useTranslation } from 'next-i18next';
import { NextSeo } from 'next-seo';

import ResponderIcon from '@Components/Common/Icons/Dashboard/Responder';

import UserMore from '@app/components/icons/user-more';
import DashboardLayout from '@app/components/sidebar/dashboard-layout';
import ParamTab, { TabPanel } from '@app/components/ui/param-tab';
import WorkspaceGroups from '@app/components/workspace-responders/workspace-groups';
import WorkspaceResponses from '@app/components/workspace-responders/workspace-responders';
import { formConstant } from '@app/constants/locales/form';
import { groupConstant } from '@app/constants/locales/group';
import { workspaceConstant } from '@app/constants/locales/workspace';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';


export default function Responders({ workspace }: any) {
    const { t } = useTranslation();
    const { workspaceName } = useAppSelector(selectWorkspace);

    const paramTabs = [
        {
            icon: <ResponderIcon className="w-10 h-10" />,
            title: t(workspaceConstant.allResponders),
            path: 'All Responders'
        },
        {
            icon: <UserMore className="w-10 h-10" />,
            title: t(groupConstant.groups),
            path: 'Groups'
        }
    ];

    return (
        <DashboardLayout>
            <NextSeo title={t(formConstant.responders) + '| ' + workspaceName} noindex={true} nofollow={true} />
            <div className="flex flex-col">
                <ParamTab className="mb-[30px] py-0" tabMenu={paramTabs}>
                    <TabPanel className="focus:outline-none" key="All Responders">
                        <WorkspaceResponses workspace={workspace} />
                    </TabPanel>
                    <TabPanel className="focus:outline-none" key="Groups">
                        <WorkspaceGroups workspace={workspace} />
                    </TabPanel>
                </ParamTab>
            </div>
        </DashboardLayout>
    );
}

export { getAuthUserPropsWithWorkspace as getServerSideProps } from '@app/lib/serverSideProps';