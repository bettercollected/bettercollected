import React from 'react';

import { useTranslation } from 'next-i18next';
import { useRouter } from 'next/router';

import Joyride from '@Components/Joyride';
import { JoyrideStepContent, JoyrideStepTitle } from '@Components/Joyride/JoyrideStepTitleAndContent';

import ImportFormsButton from '@app/components/form-integrations/import-forms-button';
import DashboardLayout from '@app/components/sidebar/dashboard-layout';
import Button from '@app/components/ui/button';
import WorkspaceDashboardForms from '@app/components/workspace-dashboard/workspace-dashboard-forms';
import WorkspaceDashboardOverview from '@app/components/workspace-dashboard/workspace-dashboard-overview';
import environments from '@app/configs/environments';
import { buttonConstant } from '@app/constants/locales/button';
import { formConstant } from '@app/constants/locales/form';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { useAppSelector } from '@app/store/hooks';
import { JOYRIDE_CLASS, JOYRIDE_ID } from '@app/store/tours/types';
import { useGetWorkspaceFormsQuery } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';

export default function CreatorDashboard({ hasCustomDomain, ...props }: { workspace: WorkspaceDto; hasCustomDomain: boolean }) {
    const { t } = useTranslation();

    const workspace = useAppSelector(selectWorkspace);
    const router = useRouter();

    const workspaceQuery = {
        workspace_id: workspace.id
    };

    const workspaceForms = useGetWorkspaceFormsQuery<any>(workspaceQuery, { pollingInterval: 30000 });

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
                        }
                    ]}
                />
            )}
            <WorkspaceDashboardOverview workspace={workspace} />
            <div className="min-h-9 flex flex-col gap-5 md:flex-row md:items-center md:justify-between">
                <p className="sh1">{t(formConstant.recentForms)}</p>
                <div className="flex gap-3">
                    <Button
                        variant="solid"
                        className={`w-full sm:w-auto`}
                        onClick={() => {
                            router.push(`/${workspace.workspaceName}/dashboard/forms/create`);
                        }}
                    >
                        Create Form
                    </Button>
                    <ImportFormsButton className={JOYRIDE_CLASS.WORKSPACE_ADMIN_DASHBOARD_STATS_IMPORT_FORM_BUTTON} />
                </div>
            </div>
            <WorkspaceDashboardForms hasCustomDomain={hasCustomDomain} workspace={workspace} workspaceForms={workspaceForms} />
        </DashboardLayout>
    );
}

export { getAuthUserPropsWithWorkspace as getServerSideProps } from '@app/lib/serverSideProps';
