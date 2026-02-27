import cn from 'classnames';
import { useTranslation } from 'next-i18next';
import { useState } from 'react';

import BottomSheetModalWrapper from '@Components/modals/modal-wrapper/bottom-sheet-modal-wrapper';
import ManageURLs from '@Components/workspace/manage-urls';
import WorkspaceDetails from '@Components/workspace/workspace-details';

export default function WorkspaceSettingsModal({ initialIndex = 0 }: { initialIndex?: number }) {
    const { t } = useTranslation();
    const [activeTab, setActiveTab] = useState(initialIndex === 1 ? 'manage-url' : 'workspace-details');

    const tabMenu = [
        {
            title: t('WORKSPACE.SETTINGS.TABS.DETAILS'),
            path: 'workspace-details'
        },
        {
            title: t('MANAGE_URLS'),
            path: 'manage-url'
        }
    ];

    return (
        <BottomSheetModalWrapper className="!px-0 pb-10">
            <div className="lg:px-30 px-5 md:px-20">
                <div className="h2-new text-black-800 mb-2">{t('WORKSPACE.SETTINGS.DEFAULT')}</div>
                <div className="p2-new text-black-700 mb-10 max-w-[440px]">{t('WORKSPACE.SETTINGS.DESCRIPTION')}</div>
            </div>

            <div className="lg:px-30 !py-0 px-5 md:px-20">
                <div className="flex space-x-1 border-b border-gray-200 overflow-x-auto pb-0">
                    {tabMenu.map((tab) => {
                        const isActive = activeTab === tab.path;
                        return (
                            <button
                                key={tab.path}
                                onClick={() => setActiveTab(tab.path)}
                                className={cn(
                                    'flex items-center gap-2 px-4 py-2 text-sm font-medium mb-[-1px] cursor-pointer hover:bg-black-200 hover:rounded whitespace-nowrap focus:outline-none',
                                    isActive
                                        ? 'border-b-2 border-black-900 text-black-900'
                                        : 'text-gray-500 hover:text-gray-700 hover:border-gray-300'
                                )}
                            >
                                {tab.title}
                            </button>
                        );
                    })}
                </div>

                <div className="mt-4">
                    {activeTab === 'workspace-details' && (
                        <WorkspaceDetails />
                    )}
                    {activeTab === 'manage-url' && (
                        <div className="lg:px-30 px-5 md:px-20">
                            <ManageURLs />
                        </div>
                    )}
                </div>
            </div>
        </BottomSheetModalWrapper>
    );
}
