import React from 'react';

import { useTranslation } from 'next-i18next';

import Joyride from '@Components/Joyride';

import ImportFormsButton from '@app/components/form-integrations/import-forms-button';
import DashboardLayout from '@app/components/sidebar/dashboard-layout';
import WorkspaceDashboardForms from '@app/components/workspace-dashboard/workspace-dashboard-forms';
import WorkspaceDashboardOverview from '@app/components/workspace-dashboard/workspace-dashboard-overview';
import environments from '@app/configs/environments';
import { formsConstant } from '@app/constants/locales/forms';
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
                            title: <span className="sh3">Your workspace profile and title</span>,
                            content: <p className="body4">This is your workspace profile image and title. You can later change this in &quot;Manage workspace&quot; settings page.</p>,
                            target: `.${JOYRIDE_CLASS.WORKSPACE_ADMIN_DASHBOARD_INFO}`,
                            placementBeacon: 'bottom-start',
                            disableBeacon: false
                        },
                        {
                            title: <span className="sh3">Share your workspace</span>,
                            content: <p className="body4">Share your workspace in different social media platforms, or copy the link via &quot;Share&quot; button.</p>,
                            target: `.${JOYRIDE_CLASS.WORKSPACE_ADMIN_DASHBOARD_SHARE}`,
                            disableBeacon: false
                        },
                        {
                            title: <span className="sh3">Preview your public workspace</span>,
                            content: (
                                <p className="body4">
                                    This link navigates you to your public workspace portal. <br /> <br /> Public workspace portal can be viewed by everyone.
                                </p>
                            ),
                            target: `.${JOYRIDE_CLASS.WORKSPACE_ADMIN_DASHBOARD_PREVIEW}`,
                            disableBeacon: false
                        },
                        {
                            title: <span className="sh3">Total imported forms</span>,
                            content: <p className="body4">You can see your total imported forms here. If your account is on a &quot;free plan&quot; you&apos;ll be able to upgrade by clicking &quot;Import unlimited forms&quot; button.</p>,
                            target: `.${JOYRIDE_CLASS.WORKSPACE_ADMIN_DASHBOARD_STATS_FORMS}`,
                            disableBeacon: false
                        },
                        {
                            title: <span className="sh3">Total imported responses</span>,
                            content: <p className="body4">Here you&apos;ll be able to see all the responses count from every forms that you have imported.</p>,
                            target: `.${JOYRIDE_CLASS.WORKSPACE_ADMIN_DASHBOARD_STATS_RESPONSES}`,
                            disableBeacon: false
                        },
                        {
                            title: <span className="sh3">Total deletion requests</span>,
                            content: <p className="body4">Here you&apos;ll be able to see total number of deletion requests you receive from the responders.</p>,
                            target: `.${JOYRIDE_CLASS.WORKSPACE_ADMIN_DASHBOARD_STATS_DELETION_REQUESTS}`,
                            disableBeacon: false
                        },
                        {
                            title: <span className="sh3">Import forms</span>,
                            content: <p className="body4">You can import your forms from using &quot;Import Forms&quot; button.</p>,
                            target: `.${JOYRIDE_CLASS.WORKSPACE_ADMIN_DASHBOARD_STATS_IMPORT_FORM_BUTTON}`,
                            placementBeacon: 'bottom-start',
                            disableBeacon: false
                        },
                        {
                            title: <span className="sh3">Your workspace</span>,
                            content: <p className="body4">This is your current active workspace. You can switch to other workspaces, or create your own new personal workspace from here.</p>,
                            target: `.${JOYRIDE_CLASS.WORKSPACE_SWITCHER}`,
                            disableBeacon: false
                        },
                        {
                            title: <span className="sh3">Workspace navigations</span>,
                            content: <p className="body4">Using these navigation links, you can navigate to your imported forms, responses, and deletion requests.</p>,
                            target: `.${JOYRIDE_CLASS.WORKSPACE_NAVIGATION}`,
                            disableBeacon: false
                        },
                        {
                            title: <span className="sh3">Advance navigations</span>,
                            content: <p className="body4">Using these navigation links, you can navigate to workspace settings, update your workspace, manage members, and many more.</p>,
                            target: `.${JOYRIDE_CLASS.WORKSPACE_ADVANCE_NAVIGATION}`,
                            disableBeacon: false
                        }
                    ]}
                />
            )}
            <WorkspaceDashboardOverview workspace={workspace} workspaceStats={workspaceStats?.data} />
            <div className="min-h-9 flex flex-col gap-5 md:flex-row md:items-center md:justify-between">
                <p className="sh1">{t(formsConstant.recentForms)}</p>
                <ImportFormsButton className={JOYRIDE_CLASS.WORKSPACE_ADMIN_DASHBOARD_STATS_IMPORT_FORM_BUTTON} />
            </div>
            <WorkspaceDashboardForms hasCustomDomain={hasCustomDomain} workspace={workspace} workspaceForms={workspaceForms} />
        </DashboardLayout>
    );
}

export { getAuthUserPropsWithWorkspace as getServerSideProps } from '@app/lib/serverSideProps';
