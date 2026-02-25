'use client';

import cn from 'classnames';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import React from 'react';
import { useTranslation } from 'react-i18next';

import Divider from '@Components/Common/DataDisplay/Divider';
import { DotIcon } from '@Components/Common/Icons/Common/DotIcon';
import SettingsIcon from '@Components/Common/Icons/Common/Settings';
import FormProviderIcon from '@Components/Common/Icons/Form/FormProviderIcon';
import Preview from '@Components/Common/Icons/Form/Preview';
import { ChevronLeft } from 'lucide-react';

import FullScreenLoader from '@app/Components/ui/fullscreen-loader';
import { localesCommon } from '@app/constants/locales/common';
import TopNavLayout from '@app/layouts/top-navbar-layout';
import { utcToLocalDate } from '@app/utils/dateUtils';
import { useSubmissionContext } from './SubmissionContext';

export default function SubmissionLayoutClient({ children }: { children: React.ReactNode }) {
    const { data, isLoading, isError, hasCustomDomain, workspaceName } = useSubmissionContext();
    const form: any = data ?? {};
    const router = useRouter();
    const pathname = usePathname();
    const { t } = useTranslation();

    const goToSubmissions = () => {
        let pathName;
        if (hasCustomDomain) {
            pathName = '';
        } else if (workspaceName) {
            pathName = `/${workspaceName}`;
        } else {
            pathName = '';
        }
        router.push(`${pathName}/my-submissions`);
    };

    const isSettings = pathname?.endsWith('/settings');
    const basePath = isSettings ? pathname.replace('/settings', '') : pathname?.replace('/form', '');

    // Check if we are at root (e.g. just [id]), then form/settings links need to append
    // If pathname is .../[id], then basePath is pathname.

    const tabs = [
        {
            icon: <Preview className="h-5 w-5" />,
            title: 'Form',
            path: 'form'
        },
        {
            icon: <SettingsIcon className="h-5 w-5" />,
            title: t(localesCommon.settings),
            path: 'settings'
        }
    ];

    if (isLoading || isError || !data) {
        return (
            <FullScreenLoader />
        );
    }

    return (
        <TopNavLayout className="bg-white !px-0" showAuthAccount={false} isCustomDomain={hasCustomDomain} isClientDomain={!hasCustomDomain} showNavbar={true}>
            <div className="mt-5 flex flex-col pb-6">
                <div className="w-full px-5">
                    <div className="flex w-fit items-center justify-start gap-2 " onClick={goToSubmissions}>
                        <ChevronLeft className="cursor-pointer" strokeWidth={2} width={24} height={24} />
                        <span className="text-black-800 cursor-pointer text-sm">Form Page</span>
                        <ChevronLeft className="text-black-600 " strokeWidth={1} width={24} height={24} />
                        <span className="text-black-600  text-sm"> My response</span>
                    </div>
                </div>
                <div className="mt-12 flex w-full flex-col gap-2 px-5 md:px-10 lg:px-28">
                    <span className="!text-pink h2-new">{form?.form?.title || 'Untitled Form'}</span>
                    <div className="text-black-600 flex flex-wrap items-center gap-2 text-sm">
                        <FormProviderIcon provider={form?.form?.settings?.provider} />
                        <DotIcon />
                        <div className="min-w-fit">Submitted: {utcToLocalDate(form?.response?.createdAt)}</div>
                    </div>
                    <Divider className="mt-2" />
                </div>

                <div className="w-full mt-3 px-5 md:px-10 lg:px-28">
                    <div className="flex space-x-1 border-b border-gray-200 overflow-x-auto pb-0">
                        {tabs.map((tab) => {
                            const isActive = pathname?.endsWith(`/${tab.path}`);
                            return (
                                <Link
                                    key={tab.path}
                                    href={`${basePath}/${tab.path}`}
                                    className={cn(
                                        'flex items-center border-b-2 gap-2 px-4 py-2 text-sm font-medium cursor-pointer hover:bg-black-200 hover:rounded whitespace-nowrap focus:outline-none',
                                        isActive
                                            ? 'border-black-900 text-black-900'
                                            : 'text-gray-500 border-transparent hover:text-gray-700'
                                    )}
                                >
                                    {tab.icon}
                                    {tab.title}
                                </Link>
                            );
                        })}
                    </div>

                    <div className="mt-4">
                        {children}
                    </div>
                </div>
            </div>
        </TopNavLayout>
    );
}
