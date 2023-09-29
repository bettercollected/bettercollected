import React from 'react';

import { useTranslation } from 'next-i18next';
import { useRouter } from 'next/router';

import CreateFormButton from '@Components/Common/CreateFormButton';
import Joyride from '@Components/Joyride';
import { JoyrideStepContent, JoyrideStepTitle } from '@Components/Joyride/JoyrideStepTitleAndContent';

import ImportFormsButton from '@app/components/form-integrations/import-forms-button';
import DashboardLayout from '@app/components/sidebar/dashboard-layout';
import WorkspaceDashboardForms from '@app/components/workspace-dashboard/workspace-dashboard-forms';
import WorkspaceDashboardOverview from '@app/components/workspace-dashboard/workspace-dashboard-overview';
import environments from '@app/configs/environments';
import { localesCommon } from '@app/constants/locales/common';
import { formConstant } from '@app/constants/locales/form';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { useAppSelector } from '@app/store/hooks';
import { JOYRIDE_CLASS, JOYRIDE_ID } from '@app/store/tours/types';
import { useGetWorkspaceFormsQuery } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';

export default function CreatorDashboard({ hasCustomDomain, ...props }: { workspace: WorkspaceDto; hasCustomDomain: boolean }) {
    const { t } = useTranslation();

    const { t: builderTranslation } = useTranslation('builder');

    const workspace = useAppSelector(selectWorkspace);
    const router = useRouter();

    const workspaceQuery = {
        workspace_id: workspace.id
    };

    const workspaceForms = useGetWorkspaceFormsQuery<any>(workspaceQuery, { pollingInterval: 30000 });

    return (
        <DashboardLayout boxClassName="bg-black-100">
            {environments.ENABLE_JOYRIDE_TOURS && (
                <Joyride
                    id={JOYRIDE_ID.WORKSPACE_ADMIN_DASHBOARD_OVERVIEW}
                    scrollOffset={68}
                    placement="bottom-end"
                    steps={[
                        {
                            title: <JoyrideStepTitle text="Your workspace profile and title" />,
                            content: <JoyrideStepContent>This is your workspace profile image and title. You can later change this in &quot;Manage workspace&quot; settings page.</JoyrideStepContent>,
                            target: `.${JOYRIDE_CLASS.WORKSPACE_ADMIN_DASHBOARD_INFO}`,
                            placementBeacon: 'bottom-end',
                            disableBeacon: false
                        },
                        {
                            title: <JoyrideStepTitle text="Workspace Collaborators" />,
                            content: <JoyrideStepContent>Invite others to collaborate on your workspace.</JoyrideStepContent>,
                            target: `.${JOYRIDE_CLASS.WORKSPACE_ADMIN_DASHBOARD_COLLABORATORS}`,
                            placementBeacon: 'bottom-end',
                            disableBeacon: false
                        },

                        {
                            title: <JoyrideStepTitle text="Share your workspace" />,
                            content: <JoyrideStepContent>Share your workspace in different social media platforms, or copy the link via &quot;Share&quot; button.</JoyrideStepContent>,
                            target: `.${JOYRIDE_CLASS.WORKSPACE_ADMIN_DASHBOARD_SHARE}`,
                            placementBeacon: 'bottom-end',
                            disableBeacon: false
                        },
                        {
                            title: <JoyrideStepTitle text="Preview your public workspace" />,
                            content: (
                                <JoyrideStepContent>
                                    This link navigates you to your public workspace portal. <br /> <br /> Public workspace portal can be viewed by everyone.
                                </JoyrideStepContent>
                            ),
                            target: `.${JOYRIDE_CLASS.WORKSPACE_ADMIN_DASHBOARD_PREVIEW}`,
                            placementBeacon: 'bottom-end',
                            disableBeacon: false
                        },
                        {
                            title: <JoyrideStepTitle text="Edit your workspace" />,
                            content: <JoyrideStepContent>Customize your workspace with your own name and logo.</JoyrideStepContent>,
                            target: `.${JOYRIDE_CLASS.WORKSPACE_ADMIN_DASHBOARD_EDIT}`,
                            placementBeacon: 'bottom-end',
                            disableBeacon: false
                        }
                    ]}
                />
            )}
            <div className="bg-white pt-4 pb-5 px-5 lg:px-10 shadow-lg">
                <WorkspaceDashboardOverview workspace={workspace} />
            </div>
            <div className="px-5 pt-12 lg:px-10">
                <WorkspaceDashboardForms hasCustomDomain={hasCustomDomain} workspace={workspace} workspaceForms={workspaceForms} />
            </div>
        </DashboardLayout>
    );
}

export { getAuthUserPropsWithWorkspace as getServerSideProps } from '@app/lib/serverSideProps';
