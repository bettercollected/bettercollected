'use client';

import { useState } from 'react';

import cn from 'classnames';
import { useTranslation } from 'react-i18next';

import { ChevronLeft, Copy, Settings } from 'lucide-react';

import { useToast } from '@app/shadcn/components/ui/use-toast';

import WorkspaceFormsTabContent from '@app/components/dashboard/workspace-forms-tab-content';
import WorkspaceResponsesTabContent from '@app/components/dashboard/workspace-responses-tab-content';
import Globe from '@app/components/icons/flags/globe';
import { HistoryIcon } from '@app/components/icons/history';
import { TrashIcon } from '@app/components/icons/trash';
import { localesCommon } from '@app/constants/locales/common';
import { formConstant } from '@app/constants/locales/form';
import { useAppSelector } from '@app/store/hooks';
import { useWorkspaceSettingsView } from '@app/store/jotai/workspace-settings-view';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { getWorkspaceShareURL } from '@app/utils/workspace-utils';
import { FormIcon } from '@Components/icons/form-icon';
import OpenLinkIcon from '@Components/icons/open-link';
import SearchBySubmissionNumber from '@Components/responder-portal/search-by-submission-number';
import WorkspaceDetailsCard from '@Components/responder-portal/workspace-details-card';
import WorkspaceSettingsContent from '@Components/workspace/workspace-settings-content';

// The creator's mirror of the public workspace, presented as what it is: a
// PAGE THAT LIVES AT A URL. A browser-style frame carries the real public
// address (copy / open live in the chrome, where those actions belong), and
// the workspace-settings gear sits on the chrome too — creator controls on
// the frame, never inside the mirrored content responders actually see.
// The content itself is the portal's own components (same tabs, same cards,
// same receipt search), so the mirror can't drift from the portal. The
// portal's identity furniture (verify-email card, responder account card,
// powered-by) is deliberately not mirrored — redundant or misleading inside
// the signed-in dashboard.
export default function CreatorDashboardClient({ hasCustomDomain }: { hasCustomDomain: boolean }) {
    const { t } = useTranslation();
    const { toast } = useToast();
    const workspace = useAppSelector(selectWorkspace);
    // Set by the sidebar "Workspace settings" item before it navigates here;
    // deliberately sticky across visits (an unmount reset would misfire under
    // strict-mode double effects and close the view it just opened).
    const { settingsViewOpen, setSettingsViewOpen } = useWorkspaceSettingsView();
    const [activeTab, setActiveTab] = useState<'forms' | 'my-submissions' | 'deletion-requests'>('forms');

    const publicUrl = getWorkspaceShareURL(workspace);

    const tabs = [
        { key: 'forms' as const, icon: <FormIcon />, title: t(localesCommon.forms) },
        { key: 'my-submissions' as const, icon: <HistoryIcon className="h-5 w-5" />, title: t(formConstant.submittedForms) },
        { key: 'deletion-requests' as const, icon: <TrashIcon className="h-5 w-5" />, title: t(formConstant.deletionRequests) }
    ];

    return (
        <div className="border-black-300 shadow-formCardDefault flex flex-col overflow-hidden rounded-xl border bg-white">
            {/* Browser chrome: dots · address pill (globe + URL + copy) · open · settings gear */}
            <div className="border-black-300 flex items-center gap-3 border-b bg-white px-4 py-2.5">
                <div className="hidden items-center gap-1.5 sm:flex" aria-hidden="true">
                    <span className="bg-black-300 h-2.5 w-2.5 rounded-full" />
                    <span className="bg-black-300 h-2.5 w-2.5 rounded-full" />
                    <span className="bg-black-300 h-2.5 w-2.5 rounded-full" />
                </div>
                <div className="bg-black-100 flex min-w-0 flex-1 items-center gap-2 rounded-full px-3 py-1.5">
                    <Globe width={14} height={14} className="text-black-600 shrink-0" />
                    <span className="text-black-700 truncate font-mono text-xs" title={publicUrl}>
                        {publicUrl}
                    </span>
                    <button
                        type="button"
                        title="Copy link"
                        aria-label="Copy your site’s link"
                        className="text-black-600 hover:text-black-900 ml-auto shrink-0"
                        onClick={() => {
                            navigator.clipboard.writeText(publicUrl);
                            toast({ description: 'Copied' });
                        }}
                    >
                        <Copy className="h-3.5 w-3.5" />
                    </button>
                </div>
                <a
                    href={publicUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    title="Open the live page"
                    aria-label="Open your live site"
                    className="text-black-600 hover:text-black-900 hover:bg-black-100 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg"
                >
                    <OpenLinkIcon />
                </a>
                <button
                    type="button"
                    title="Site settings"
                    aria-label="Site settings"
                    aria-pressed={settingsViewOpen}
                    onClick={() => setSettingsViewOpen(!settingsViewOpen)}
                    className={cn(
                        'flex h-8 w-8 shrink-0 items-center justify-center rounded-lg',
                        settingsViewOpen ? 'bg-[#E9EFFC] text-[#2456CC]' : 'text-black-600 hover:text-black-900 hover:bg-black-100'
                    )}
                >
                    <Settings className="h-[18px] w-[18px]" />
                </button>
            </div>

            {/* Settings render INSIDE the frame — the gear opens the site's
                settings page, you close it and you're back on the page you
                were configuring. (Previously a bottom sheet over everything.) */}
            {settingsViewOpen && (
                <div className="bg-white py-6">
                    <button type="button" onClick={() => setSettingsViewOpen(false)} className="text-black-600 hover:text-black-900 mb-4 flex items-center gap-1 px-5 text-sm font-medium md:px-10">
                        <ChevronLeft className="h-4 w-4" />
                        Back to page
                    </button>
                    <WorkspaceSettingsContent showUrlRow={false} />
                </div>
            )}

            {/* The "page": the portal's surface colour and content. */}
            <div className={cn('flex-col gap-4 bg-[#F6F8FC] p-5 md:flex-row md:p-8', settingsViewOpen ? 'hidden' : 'flex')}>
                <div className="flex flex-col gap-4 md:w-[320px] md:max-w-[320px]">
                    <WorkspaceDetailsCard workspace={workspace} />
                    {/* Same sidebar placement as the portal: one utility
                        column, two-column page. */}
                    <SearchBySubmissionNumber className="w-full" />
                </div>
                <div className="flex min-w-0 flex-1 flex-col">
                    <div className="border-black-300 flex space-x-1 overflow-x-auto border-b pb-0">
                        {tabs.map((tab) => {
                            const isActive = activeTab === tab.key;
                            return (
                                <button
                                    key={tab.key}
                                    type="button"
                                    onClick={() => setActiveTab(tab.key)}
                                    className={cn(
                                        'mb-[-1px] flex cursor-pointer items-center gap-2 whitespace-nowrap border-b-2 px-4 py-2 text-sm font-medium transition-colors focus:outline-none',
                                        isActive ? 'border-[#2456CC] text-black-900' : 'text-black-600 hover:text-black-900 border-transparent'
                                    )}
                                >
                                    {tab.icon}
                                    {tab.title}
                                </button>
                            );
                        })}
                    </div>
                    <div className="mt-4 min-w-0">
                        {activeTab === 'forms' && <WorkspaceFormsTabContent workspace={workspace} publicBaseUrl={publicUrl} />}
                        {activeTab === 'my-submissions' && <WorkspaceResponsesTabContent workspace={workspace} />}
                        {activeTab === 'deletion-requests' && <WorkspaceResponsesTabContent workspace={workspace} deletionRequests />}
                    </div>
                </div>
            </div>
        </div>
    );
}
