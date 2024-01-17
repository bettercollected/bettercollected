import React from 'react';

import {useTranslation} from 'next-i18next';

import Joyride from '@Components/Joyride';
import {JoyrideStepContent, JoyrideStepTitle} from '@Components/Joyride/JoyrideStepTitleAndContent';

import DashboardLayout from '@app/components/sidebar/dashboard-layout';
import WorkspaceDashboardForms from '@app/components/workspace-dashboard/workspace-dashboard-forms';
import WorkspaceDashboardOverview from '@app/components/workspace-dashboard/workspace-dashboard-overview';
import WorkspaceDashboardPinnedForms from '@app/components/workspace-dashboard/workspace-dashboard-pinned-forms';
import environments from '@app/configs/environments';
import {WorkspaceDto} from '@app/models/dtos/workspaceDto';
import {useAppSelector} from '@app/store/hooks';
import {JOYRIDE_CLASS, JOYRIDE_ID} from '@app/store/tours/types';
import {useGetWorkspaceFormsQuery} from '@app/store/workspaces/api';
import {selectWorkspace} from '@app/store/workspaces/slice';

export default function CreatorDashboard({hasCustomDomain, ...props}: {
    workspace: WorkspaceDto;
    hasCustomDomain: boolean
}) {
    const {t} = useTranslation();

    const {t: builderTranslation} = useTranslation('builder');

    const workspace = useAppSelector(selectWorkspace);

    const pinnedFormsQuery = {
        workspace_id: props.workspace.id,
        pinned_only: true
    };

    const pinnedFormsResponse = useGetWorkspaceFormsQuery(pinnedFormsQuery, {skip: !workspace.id});
    const pinnedForms = pinnedFormsResponse?.data?.items || [];

    return (
        <DashboardLayout boxClassName="bg-black-100">
            {environments.ENABLE_JOYRIDE_TOURS && (
                <Joyride
                    id={JOYRIDE_ID.WORKSPACE_ADMIN_DASHBOARD_OVERVIEW}
                    scrollOffset={68}
                    placement="bottom-end"
                    steps={[
                        {
                            title: <JoyrideStepTitle text="Your workspace profile and title"/>,
                            content: <JoyrideStepContent>This is your workspace profile image and title. You can later
                                change this in &quot;Manage workspace&quot; settings page.</JoyrideStepContent>,
                            target: `.${JOYRIDE_CLASS.WORKSPACE_ADMIN_DASHBOARD_INFO}`,
                            placementBeacon: 'bottom-end',
                            disableBeacon: false
                        },
                        {
                            title: <JoyrideStepTitle text="Workspace Collaborators"/>,
                            content: <JoyrideStepContent>Invite others to collaborate on your
                                workspace.</JoyrideStepContent>,
                            target: `.${JOYRIDE_CLASS.WORKSPACE_ADMIN_DASHBOARD_COLLABORATORS}`,
                            placementBeacon: 'bottom-end',
                            disableBeacon: false
                        },

                        {
                            title: <JoyrideStepTitle text="Share your workspace"/>,
                            content: <JoyrideStepContent>Share your workspace in different social media platforms, or
                                copy the link via &quot;Share&quot; button.</JoyrideStepContent>,
                            target: `.${JOYRIDE_CLASS.WORKSPACE_ADMIN_DASHBOARD_SHARE}`,
                            placementBeacon: 'bottom-end',
                            disableBeacon: false
                        },
                        {
                            title: <JoyrideStepTitle text="Preview your public workspace"/>,
                            content: (
                                <JoyrideStepContent>
                                    This link navigates you to your public workspace portal. <br/> <br/> Public
                                    workspace portal can be viewed by everyone.
                                </JoyrideStepContent>
                            ),
                            target: `.${JOYRIDE_CLASS.WORKSPACE_ADMIN_DASHBOARD_PREVIEW}`,
                            placementBeacon: 'bottom-end',
                            disableBeacon: false
                        },
                        {
                            title: <JoyrideStepTitle text="Edit your workspace"/>,
                            content: <JoyrideStepContent>Customize your workspace with your own name and
                                logo.</JoyrideStepContent>,
                            target: `.${JOYRIDE_CLASS.WORKSPACE_ADMIN_DASHBOARD_EDIT}`,
                            placementBeacon: 'bottom-end',
                            disableBeacon: false
                        }
                    ]}
                />
            )}
            <div className="bg-white pt-4 pb-5 px-5 lg:px-10 shadow-overview">
                <WorkspaceDashboardOverview workspace={props.workspace}/>
            </div>
            <div className="px-5 pt-12 lg:px-10">
                {pinnedForms?.length > 0 &&
                    <WorkspaceDashboardPinnedForms workspacePinnedForms={pinnedFormsResponse} title={t('PINNED_FORMS')}
                                                   workspace={workspace} hasCustomDomain={hasCustomDomain}/>}
                <WorkspaceDashboardForms isWorkspace showButtons={pinnedForms?.length === 0} workspace={workspace}
                                         hasCustomDomain={hasCustomDomain}/>
            </div>
        </DashboardLayout>
    );
}

export {getAuthUserPropsWithWorkspace as getServerSideProps} from '@app/lib/serverSideProps';
