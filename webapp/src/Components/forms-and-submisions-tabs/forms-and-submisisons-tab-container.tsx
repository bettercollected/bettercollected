import { useState } from 'react';
import { useTranslation } from 'next-i18next';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import cn from 'classnames';

import { FormIcon } from '@Components/Common/Icons/Form/FormIcon';

import WorkspaceFormsTabContent from '@Components/dashboard/workspace-forms-tab-content';
import WorkspaceResponsesTabContent from '@Components/dashboard/workspace-responses-tab-content';
import { HistoryIcon } from '@app/Components/icons/history';
import { TrashIcon } from '@app/Components/icons/trash';
import { localesCommon } from '@app/constants/locales/common';
import { formConstant } from '@app/constants/locales/form';

interface ISubmissionTabContainer {
    workspaceId: string;
    showResponseBar: boolean;
    workspace: any;
    isFormCreator?: boolean;
    isPreview?: boolean;
}

export default function FormsAndSubmissionsTabContainer({ showResponseBar, workspace, isFormCreator = false, isPreview = false }: ISubmissionTabContainer) {
    const { t } = useTranslation();
    const router = useRouter();
    const pathname = usePathname();
    const searchParams = useSearchParams();

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

    const initialTab = searchParams?.get('view') || 'forms';
    const [localTab, setLocalTab] = useState(initialTab);
    const activeTab = (isPreview || !searchParams?.get('view')) ? localTab : searchParams?.get('view');

    const handleTabChange = (path: string) => {
        setLocalTab(path);
        if (!isPreview) {
            const params = new URLSearchParams(searchParams?.toString());
            params.set('view', path);
            router.push(`${pathname}?${params.toString()}`, { scroll: false });
        }
    };

    return (
        <div className="flex flex-col md:pl-12 !pb-4">
            <div className="flex space-x-1 border-b border-gray-200 overflow-x-auto pb-0">
                {paramTabs.map((tab) => {
                    const isActive = activeTab === tab.path;
                    return (
                        <button
                            key={tab.path}
                            onClick={() => handleTabChange(tab.path)}
                            className={cn(
                                'flex items-center gap-2 px-4 py-2 text-sm font-medium mb-[-1px] cursor-pointer hover:bg-black-200 hover:rounded whitespace-nowrap focus:outline-none',
                                isActive
                                    ? 'border-b-2 border-black-900 text-black-900'
                                    : 'text-gray-500 hover:text-gray-700 hover:border-gray-300'
                            )}
                        >
                            {tab.icon}
                            {tab.title}
                        </button>
                    );
                })}
            </div>

            <div className="mt-4">
                {activeTab === 'forms' && (
                    <WorkspaceFormsTabContent isFormCreator={isFormCreator} workspace={workspace} />
                )}
                {activeTab === 'my-submissions' && (
                    <WorkspaceResponsesTabContent workspace={workspace} />
                )}
                {activeTab === 'deletion-requests' && showResponseBar && (
                    <WorkspaceResponsesTabContent workspace={workspace} deletionRequests />
                )}
            </div>
        </div>
    );
}
