import cn from 'classnames';
import { useTranslation } from 'react-i18next';
import { useState } from 'react';

import ManageURLs from '@Components/workspace/manage-urls';
import WorkspaceDetails from '@Components/workspace/workspace-details';

/**
 * The workspace-settings surface (header, Details / Manage URLs tabs and
 * panels), independent of its container. The Public Workspace mirror renders
 * it inside its browser frame; the bottom-sheet modal (used by the
 * URL-update deep links) wraps the same component — one settings surface,
 * two containers, no drift.
 *
 * One horizontal padding, applied ONCE here: header, tabs and panel content
 * all start on the same left edge (the panels used to add their own px-20+
 * on top, indenting content past the tabs above it).
 */
export default function WorkspaceSettingsContent({ initialIndex = 0, showUrlRow = true }: { initialIndex?: number; showUrlRow?: boolean }) {
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
        <div className="px-5 md:px-10">
            <div className="h2-new text-black-800 mb-2">{t('WORKSPACE.SETTINGS.DEFAULT')}</div>
            <div className="p2-new text-black-700 mb-8 max-w-[520px]">{t('WORKSPACE.SETTINGS.DESCRIPTION')}</div>

            <div className="border-black-300 flex space-x-1 overflow-x-auto border-b pb-0">
                {tabMenu.map((tab) => {
                    const isActive = activeTab === tab.path;
                    return (
                        <button
                            key={tab.path}
                            onClick={() => setActiveTab(tab.path)}
                            className={cn(
                                'flex items-center gap-2 px-4 py-2 text-sm font-medium mb-[-1px] cursor-pointer whitespace-nowrap border-b-2 transition-colors focus:outline-none',
                                isActive ? 'border-[#2456CC] text-black-900' : 'text-black-600 hover:text-black-800 border-transparent'
                            )}
                        >
                            {tab.title}
                        </button>
                    );
                })}
            </div>

            <div className="mt-6">
                {activeTab === 'workspace-details' && <WorkspaceDetails showUrlRow={showUrlRow} />}
                {activeTab === 'manage-url' && <ManageURLs />}
            </div>
        </div>
    );
}
