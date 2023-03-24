import React from 'react';

import AllSubmissionTab from '@app/components/dashboard/all-submission-tab';
import { HistoryIcon } from '@app/components/icons/history';
import { TrashIcon } from '@app/components/icons/trash';
import SidebarLayout from '@app/components/sidebar/sidebar-layout';
import ParamTab from '@app/components/ui/param-tab';
import { TabPanel } from '@app/components/ui/tab';
import { getAuthUserPropsWithWorkspace } from '@app/lib/serverSideProps';

export default function MySubmissions({ workspace }: { workspace: any }) {
    const paramTabs = [
        {
            icon: <HistoryIcon className="w-[20px] h-[20px]" />,
            title: 'All Submissions',
            path: 'all'
        },
        {
            icon: <TrashIcon className="w-[20px] h-[20px]" />,
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
                    <AllSubmissionTab workspace_id={workspace.id} requestedForDeletionOnly />
                </TabPanel>
            </ParamTab>
        </SidebarLayout>
    );
}

export async function getServerSideProps(_context: any) {
    return await getAuthUserPropsWithWorkspace(_context);
}
