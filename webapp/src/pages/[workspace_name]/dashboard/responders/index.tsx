import React from 'react';

import { useTranslation } from 'next-i18next';

import DashboardLayout from '@app/components/sidebar/dashboard-layout';
import ParamTab, { TabPanel } from '@app/components/ui/param-tab';
import WorkspaceGroups from '@app/components/workspace-responders/workspace-groups';
import WorkspaceResponses from '@app/components/workspace-responders/workspace-responders';
import { formConstant } from '@app/constants/locales/form';
import { groupConstant } from '@app/constants/locales/group';
import { workspaceConstant } from '@app/constants/locales/workspace';

export default function Responders({ workspace }: any) {
    const { t } = useTranslation();

    const paramTabs = [
        {
            title: t(workspaceConstant.allResponders),
            path: 'All Responders'
        },
        {
            title: t(groupConstant.groups),
            path: 'Groups'
        }
    ];

    return (
        <DashboardLayout>
            <div className="flex flex-col py-4">
                <div className="h4">{t(formConstant.responders)}</div>
                <ParamTab className="my-10  pb-0 border-b  border-black-500" tabMenu={paramTabs}>
                    <TabPanel className="focus:outline-none" key="All Responders">
                        <WorkspaceResponses workspace={workspace} />
                    </TabPanel>
                    <TabPanel className="focus:outline-none" key="Groups">
                        <WorkspaceGroups />
                    </TabPanel>
                </ParamTab>
            </div>
        </DashboardLayout>
    );
}

export { getAuthUserPropsWithWorkspace as getServerSideProps } from '@app/lib/serverSideProps';
