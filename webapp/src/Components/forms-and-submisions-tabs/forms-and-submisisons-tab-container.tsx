import { useTranslation } from 'next-i18next';

import { FormIcon } from '@Components/Common/Icons/Form/FormIcon';

import WorkspaceFormsTabContent from '@Components/dashboard/workspace-forms-tab-content';
import WorkspaceResponsesTabContent from '@Components/dashboard/workspace-responses-tab-content';
import { HistoryIcon } from '@app/Components/icons/history';
import { TrashIcon } from '@app/Components/icons/trash';
import ParamTab, { TabPanel } from '@app/Components/ui/param-tab';
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
        <ParamTab className="md:!pt-0 !mb-0 md:pl-12 !pb-4" tabMenu={paramTabs}>
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
