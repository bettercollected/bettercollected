import React from 'react';

import { useTranslation } from 'next-i18next';

import Joyride from '@Components/Joyride';
import { JoyrideStepContent, JoyrideStepTitle } from '@Components/Joyride/JoyrideStepTitleAndContent';

import ImportFormsButton from '@app/components/form-integrations/import-forms-button';
import DashboardLayout from '@app/components/sidebar/dashboard-layout';
import WorkspaceDashboardForms from '@app/components/workspace-dashboard/workspace-dashboard-forms';
import WorkspaceDashboardOverview from '@app/components/workspace-dashboard/workspace-dashboard-overview';
import environments from '@app/configs/environments';
import { formConstant } from '@app/constants/locales/form';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { JOYRIDE_CLASS, JOYRIDE_ID } from '@app/store/tours/types';
import { useGetWorkspaceFormsQuery, useGetWorkspaceStatsQuery } from '@app/store/workspaces/api';

export default function CreatorDashboard({ workspace, hasCustomDomain, ...props }: { workspace: WorkspaceDto; hasCustomDomain: boolean }) {
    const { t } = useTranslation();

    const workspaceQuery = {
        workspace_id: workspace.id
    };

    const workspaceForms = useGetWorkspaceFormsQuery<any>(workspaceQuery, { pollingInterval: 30000 });
    const workspaceStats = useGetWorkspaceStatsQuery(workspace?.id, { pollingInterval: 30000 });

    return (
        <DashboardLayout>
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
                            placementBeacon: 'bottom-start',
                            disableBeacon: false
                        },
                        {
                            title: <JoyrideStepTitle text="Share your workspace" />,
                            content: <JoyrideStepContent>Share your workspace in different social media platforms, or copy the link via &quot;Share&quot; button.</JoyrideStepContent>,
                            target: `.${JOYRIDE_CLASS.WORKSPACE_ADMIN_DASHBOARD_SHARE}`,
                            placementBeacon: 'bottom-start',
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
                            placementBeacon: 'bottom-start',
                            disableBeacon: false
                        },
                        {
                            title: <JoyrideStepTitle text="Total imported forms" />,
                            content: <JoyrideStepContent>You can see your total imported forms here. If your account is on a &quot;free plan&quot; you&apos;ll be able to upgrade by clicking &quot;Import unlimited forms&quot; button.</JoyrideStepContent>,
                            target: `.${JOYRIDE_CLASS.WORKSPACE_ADMIN_DASHBOARD_STATS_FORMS}`,
                            placementBeacon: 'bottom-start',
                            disableBeacon: false
                        },
                        {
                            title: <JoyrideStepTitle text="Total imported responses" />,
                            content: <JoyrideStepContent>Here you&apos;ll be able to see all the responses count from every forms that you have imported.</JoyrideStepContent>,
                            target: `.${JOYRIDE_CLASS.WORKSPACE_ADMIN_DASHBOARD_STATS_RESPONSES}`,
                            placementBeacon: 'bottom-start',
                            disableBeacon: false
                        },
                        {
                            title: <JoyrideStepTitle text="Total deletion requests" />,
                            content: <JoyrideStepContent>Here you&apos;ll be able to see total number of deletion requests you receive from the responders.</JoyrideStepContent>,
                            target: `.${JOYRIDE_CLASS.WORKSPACE_ADMIN_DASHBOARD_STATS_DELETION_REQUESTS}`,
                            placementBeacon: 'bottom-start',
                            disableBeacon: false
                        },
                        {
                            title: <JoyrideStepTitle text="Import forms" />,
                            content: <JoyrideStepContent>You can import your forms from using &quot;Import Forms&quot; button.</JoyrideStepContent>,
                            target: `.${JOYRIDE_CLASS.WORKSPACE_ADMIN_DASHBOARD_STATS_IMPORT_FORM_BUTTON}`,
                            placementBeacon: 'bottom-start',
                            disableBeacon: false
                        },
                        {
                            title: <JoyrideStepTitle text="Your workspace" />,
                            content: <JoyrideStepContent>This is your current active workspace. You can switch to other workspaces, or create your own new personal workspace from here.</JoyrideStepContent>,
                            target: `.${JOYRIDE_CLASS.WORKSPACE_SWITCHER}`,
                            placementBeacon: 'top-end',
                            disableBeacon: false
                        },
                        {
                            title: <JoyrideStepTitle text="Workspace navigations" />,
                            content: <JoyrideStepContent>Using these navigation links, you can navigate to your imported forms, responses, and deletion requests.</JoyrideStepContent>,
                            target: `.${JOYRIDE_CLASS.WORKSPACE_NAVIGATION}`,
                            placementBeacon: 'top-end',
                            disableBeacon: false
                        },
                        {
                            title: <span className="sh3">Advance navigations</span>,
                            content: <JoyrideStepContent>Using these navigation links, you can navigate to workspace settings, update your workspace, manage members, and many more.</JoyrideStepContent>,
                            target: `.${JOYRIDE_CLASS.WORKSPACE_ADVANCE_NAVIGATION}`,
                            placementBeacon: 'top-end',
                            disableBeacon: false
                        }
                    ]}
                />
            )}
            <WorkspaceDashboardOverview workspace={workspace} workspaceStats={workspaceStats?.data} />
            <div className="min-h-9 flex flex-col gap-5 md:flex-row md:items-center md:justify-between">
                <p className="sh1">{t(formConstant.recentForms)}</p>
                <ImportFormsButton className={JOYRIDE_CLASS.WORKSPACE_ADMIN_DASHBOARD_STATS_IMPORT_FORM_BUTTON} />
            </div>
            <WorkspaceDashboardForms hasCustomDomain={hasCustomDomain} workspace={workspace} workspaceForms={workspaceForms} />
        </DashboardLayout>
    );
}

export { getAuthUserPropsWithWorkspace as getServerSideProps } from '@app/lib/serverSideProps';
