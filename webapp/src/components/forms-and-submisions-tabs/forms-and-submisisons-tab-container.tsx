import { useTranslation } from 'next-i18next';

import { FormIcon } from '@Components/Common/Icons/Form/FormIcon';

import WorkspaceFormsTabContent from '@app/components/dashboard/workspace-forms-tab-content';
import WorkspaceResponsesTabContent from '@app/components/dashboard/workspace-responses-tab-content';
import { HistoryIcon } from '@app/components/icons/history';
import { TrashIcon } from '@app/components/icons/trash';
import ParamTab, { TabPanel } from '@app/components/ui/param-tab';
import { localesCommon } from '@app/constants/locales/common';
import { formConstant } from '@app/constants/locales/form';

interface ISubmissionTabContainer {
    workspaceId: string;
    showResponseBar: boolean;
    workspace: any;
    isFormCreator?: boolean;
}

export default function FormsAndSubmissionsTabContainer({ showResponseBar, workspace, isFormCreator = false }: ISubmissionTabContainer) {
    const { t } = useTranslation();

    const paramTabs = [
        {
            icon: <FormIcon />,
            title: t(localesCommon.forms),
            path: 'forms'
        },
        {
            icon: <HistoryIcon className="w-5 h-5" />,
            title: t(formConstant.submittedForms),
            path: 'my-submissions'
        }
    ];

    if (showResponseBar) {
        paramTabs.push({
            icon: <TrashIcon className="w-5 h-5" />,
            title: t(formConstant.deletionRequests),
            path: 'deletion-requests'
        });
    }

    return (
        <ParamTab className="pb-[28px] !mb-0 px-5 lg:px-10 xl:px-20" tabMenu={paramTabs}>
            <TabPanel className="focus:outline-none" key="forms">
                <WorkspaceFormsTabContent isFormCreator={isFormCreator} workspace={workspace} />
            </TabPanel>
            <TabPanel className="focus:outline-none" key="my-submissions">
                <WorkspaceResponsesTabContent workspace={workspace} />
            </TabPanel>
            {showResponseBar && (
                <TabPanel className="focus:outline-none" key="deletion-requests">
                    <WorkspaceResponsesTabContent workspace={workspace} deletionRequests />
                </TabPanel>
            )}
        </ParamTab>
    );
}
