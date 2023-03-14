import React, { useEffect, useState } from 'react';

import Image from 'next/image';
import Link from 'next/link';
import { useRouter } from 'next/router';

import CalendarMonthIcon from '@mui/icons-material/CalendarMonth';
import { toast } from 'react-toastify';

import SubmissionsGrid from '@app/components/cards/submission-container';
import AllSubmissionTab from '@app/components/dashboard/all-submission-tab';
import EmptyFormsView from '@app/components/dashboard/empty-form';
import BreadcrumbRenderer from '@app/components/form/renderer/breadcrumbs-renderer';
import FormRenderer from '@app/components/form/renderer/form-renderer';
import { Google } from '@app/components/icons/brands/google';
import { HomeIcon } from '@app/components/icons/home';
import SettingsPrivacy from '@app/components/settings/workspace/settings-privacy';
import SettingsProfile from '@app/components/settings/workspace/settings-profile';
import { WorkspaceDangerZoneSettings } from '@app/components/settings/workspace/workspace-danger-zone-settings';
import SidebarLayout from '@app/components/sidebar/sidebar-layout';
import FullScreenLoader from '@app/components/ui/fullscreen-loader';
import ParamTab from '@app/components/ui/param-tab';
import { TabPanel } from '@app/components/ui/tab';
import { ToastId } from '@app/constants/toastId';
import { useBreakpoint } from '@app/lib/hooks/use-breakpoint';
import { getAuthUserPropsWithWorkspace } from '@app/lib/serverSideProps';
import { useGetWorkspaceAllSubmissionsQuery, useLazyGetWorkspaceSubmissionQuery } from '@app/store/workspaces/api';
import { toMonthDateYearStr } from '@app/utils/dateUtils';
import { toEndDottedStr } from '@app/utils/stringUtils';

export default function MySubmissions({ workspace }: { workspace: any }) {
    const paramTabs = [
        {
            title: 'All Submissions',
            path: 'all'
        },
        {
            title: 'Requested For Deletion',
            path: 'requested-for-deletion'
        }
    ];

    return (
        <SidebarLayout>
            <ParamTab tabMenu={paramTabs}>
                <TabPanel className="focus:outline-none" key="all">
                    {/*<MyRecentSubmissions/>*/}
                    <AllSubmissionTab workspace_id={workspace.id} />
                </TabPanel>
                <TabPanel className="focus:outline-none" key="requested-for-deletion">
                    <AllSubmissionTab workspace_id={workspace.id} requested_for_deletion_only={true} />
                </TabPanel>
            </ParamTab>
        </SidebarLayout>
    );
}

export async function getServerSideProps(_context: any) {
    return await getAuthUserPropsWithWorkspace(_context);
}
