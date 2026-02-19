'use client';

import React, { useState } from 'react';

import { useTranslation } from 'react-i18next';
import { useParams, useRouter, useSearchParams, usePathname } from 'next/navigation';
import cn from 'classnames';

import Divider from '@Components/Common/DataDisplay/Divider';
import Tooltip from '@Components/Common/DataDisplay/Tooltip';
import { DotIcon } from '@Components/Common/Icons/Common/DotIcon';
import SettingsIcon from '@Components/Common/Icons/Common/Settings';
import FormProviderIcon from '@Components/Common/Icons/Form/FormProviderIcon';
import Preview from '@Components/Common/Icons/Form/Preview';
import { Button } from '@app/shadcn/components/ui/button';
import { ChevronLeft } from '@mui/icons-material';

import FormRenderer from '@app/Components/Form/renderer/form-renderer';
import { useModal } from '@app/Components/modal-views/context';
import FullScreenLoader from '@app/Components/ui/fullscreen-loader';
import environments from '@app/configs/environments';
import { buttonConstant } from '@app/constants/locales/button';
import { localesCommon } from '@app/constants/locales/common';
import { toolTipConstant } from '@app/constants/locales/tooltip';
import Layout from '@app/layouts/_layout';
import { utcToLocalDate } from '@app/utils/dateUtils';

interface SubmissionProps {
    hasCustomDomain: boolean;
    data: any;
    handleRequestForDeletion: any;
}

export default function Submission({ hasCustomDomain, data, handleRequestForDeletion }: SubmissionProps) {
    const { isLoading, isError } = data;
    const form: any = data ?? {};
    const router = useRouter();
    const searchParams = useSearchParams();
    const pathname = usePathname();

    const { t } = useTranslation();
    const { openModal, closeModal } = useModal();


    const paramTabs = [
        {
            icon: <Preview className="h-5 w-5" />,
            title: 'Form',
            path: 'Form'
        },
        {
            icon: <SettingsIcon className="h-5 w-5" />,
            title: t(localesCommon.settings),
            path: 'Settings'
        }
    ];

    const params = useParams();

    const goToSubmissions = () => {
        let pathName;
        if (hasCustomDomain) {
            pathName = '/';
        } else {
            pathName = `/${params?.workspace_name}`;
        }

        router.push(`${pathName}?view=mySubmissions`);
    };

    const deletionStatus = !!form?.response?.deletionStatus;

    const handleRequestForDeletionModal = () => {
        openModal('REQUEST_FOR_DELETION_VIEW', { handleRequestForDeletion: handleRequestForDeletion });
    };

    const initialTab = searchParams?.get('view') || 'Form';
    const activeTab = initialTab;

    const handleTabChange = (path: string) => {
         const newParams = new URLSearchParams(searchParams?.toString());
         newParams.set('view', path);
         router.push(`${pathname}?${newParams.toString()}`, { scroll: false });
    };

    return (
        <Layout className="bg-white !px-0" showAuthAccount={false} isCustomDomain={hasCustomDomain} isClientDomain={!hasCustomDomain} showNavbar={true}>
            {isLoading || isError || !data ? (
                <FullScreenLoader />
            ) : (
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
                        <Divider className="mt-6" />
                    </div>
                    
                     <div className="w-full px-5 md:px-10 lg:px-28">
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
                            {activeTab === 'Form' && (
                                <div className="mt-12 w-full">
                                    <FormRenderer form={form.form} response={form.response} isDisabled />
                                </div>
                            )}

                            {activeTab === 'Settings' && (
                                <div className="flex flex-col gap-[72px] px-5 md:px-10 lg:px-28">
                                    <div className="flex flex-col gap-2">
                                        <span className="h3-new">Settings</span>
                                        <span className="p2-new text-black-700"> Review your data usage permissions</span>
                                    </div>
                                    {form?.settings?.provider !== 'self' && (
                                        <div className="flex max-w-[800px] flex-col gap-4">
                                            <Divider />
                                            <div className="h4-new">You can request for deletion of your data in this form.</div>
                                            <Divider />
                                        </div>
                                    )}
                                    {!form?.response?.deletionStatus ? (
                                        <div>
                                            <Tooltip title={deletionStatus ? t(toolTipConstant.alreadyRequestedForDeletion) : t(toolTipConstant.requestForDeletion)}>
                                                <Button className={`w-fit`} variant="danger" onClick={handleRequestForDeletionModal}>
                                                    {t(buttonConstant.requestForDeletion)}
                                                </Button>
                                            </Tooltip>
                                        </div>
                                    ) : (
                                        <div className="flex flex-col gap-2">
                                            <span className="h4-new !text-red-500 ">You have requested for deletion of your response.</span>
                                            <span>Status: Pending</span>
                                        </div>
                                    )}
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            )}
        </Layout>
    );
}
