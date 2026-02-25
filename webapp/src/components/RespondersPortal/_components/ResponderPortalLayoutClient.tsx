'use client';

import cn from 'classnames';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import React from 'react';
import { useTranslation } from 'react-i18next';

import Divider from '@Components/common/divider';
import { Button } from '@app/shadcn/components/ui/button';
import { Disclosure } from '@headlessui/react';

import { FormIcon } from '@Components/icons/form-icon';
import WorkspaceDetailsCard from '@app/components/RespondersPortal/WorkspaceDetailsCard';
import AuthAccountProfileImage from '@app/components/auth/account-profile-image';
import { ChevronDown } from '@app/components/icons/chevron-down';
import { HistoryIcon } from '@app/components/icons/history';
import { Logout } from '@app/components/icons/logout-icon';
import { TrashIcon } from '@app/components/icons/trash';
import { useModal } from '@app/components/modal-views/context';
import ActiveLink from '@app/components/ui/links/active-link';
import Logo from '@app/components/ui/logo';
import PoweredBy from '@app/components/ui/powered-by';
import { localesCommon } from '@app/constants/locales/common';
import { formConstant } from '@app/constants/locales/form';
import { profileMenu } from '@app/constants/locales/profile-menu';
import { selectAuth } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { getFullNameFromUser } from '@app/utils/userUtils';
import SearchBySubmissionNumber from '../SearchBySubmissionNumber';

export default function ResponderPortalLayoutClient({
    children,
    hasCustomDomain
}: {
    children: React.ReactNode;
    hasCustomDomain: boolean;
}) {
    const { t } = useTranslation();
    const auth = useAppSelector(selectAuth);
    const router = useRouter();
    const workspace = useAppSelector(selectWorkspace);
    const pathname = usePathname();
    const { openModal } = useModal();

    const isClientDomain = typeof window !== 'undefined' && window.location.origin !== window?.PUBLIC_CONFIG?.DASHBOARD_DOMAIN;

    const handleLogout = () => {
        openModal('LOGOUT_VIEW', { workspace, isClientDomain });
    };

    const tabs = [
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

    if (auth.id) {
        tabs.push({
            icon: <TrashIcon className="w-5 h-5" />,
            title: t(formConstant.deletionRequests),
            path: 'deletion-requests'
        });
    }

    const basePath = hasCustomDomain ? '' : `/${workspace.workspaceName}`;

    return (
        <div className={`!bg-new-white-200 max-w-screen flex h-screen max-h-screen w-screen flex-col overflow-auto p-5 opacity-100 md:flex-row md:p-10 ${!hasCustomDomain ? '!pb-20' : ''}`}>
            <div className="max-w-screen w-full md:sticky md:top-0 md:w-[320px] md:max-w-[320px]">
                <WorkspaceDetailsCard workspace={workspace} />
                {!auth.id && !auth.isLoading && (
                    <div className="mt-6 flex flex-col rounded-xl bg-white p-6">
                        <div className="h4-new">Check my data</div>
                        <div className="p2-new text-black-600 mt-2">Verify your email address to view all the data associated with you.</div>
                        <Button
                            className="mt-6"
                            size="sm"
                            onClick={() => {
                                const params = new URLSearchParams({
                                    type: 'responder',
                                    workspace_id: workspace.id,
                                    redirect_to: pathname
                                });
                                router.push(`/login?${params.toString()}`);
                            }}
                        >
                            Verify Now
                        </Button>
                    </div>
                )}
                {auth.id && (
                    <div className="mt-6 w-full  rounded-xl bg-white ">
                        <Disclosure>
                            {({ open }) => (
                                <>
                                    <Disclosure.Button className="flex w-full cursor-pointer items-center justify-between gap-2 p-4">
                                        <div className="flex gap-2">
                                            <AuthAccountProfileImage size={36} image={auth?.profileImage} name={getFullNameFromUser(auth) ?? ''} />
                                            <div className="!text-black-700 flex flex-col justify-center gap-2 pr-1 text-start">
                                                <span className="body6 !leading-none">{getFullNameFromUser(auth)?.trim() || auth?.email || ''}</span>
                                                <span className="body5 !leading-none">{auth?.email} </span>
                                            </div>
                                        </div>
                                        <ChevronDown className={`${open ? 'rotate-180 transform' : ''} h-3 w-3 text-blue-900`} />
                                    </Disclosure.Button>
                                    <Disclosure.Panel className="pb-2">
                                        {!auth?.roles?.includes('FORM_CREATOR') && (
                                            <>
                                                <Divider className="text-black-200" />
                                                <div className="p4-new text-black-600 p-4">
                                                    You have 0 workspace associated with this email.{' '}
                                                    <ActiveLink target="_blank" href="https://bettercollected.com" className="text-blue-500">
                                                        Try Bettercollected{' '}
                                                    </ActiveLink>
                                                </div>
                                            </>
                                        )}
                                        <Divider className="text-black-200" />
                                        <div className="text-black-600 hover:bg-new-blue-100 m-2 flex cursor-pointer gap-2 rounded p-2 active:bg-blue-100" onClick={handleLogout}>
                                            <Logout width={24} height={24} />
                                            <span>{t(profileMenu.logout)}</span>
                                        </div>
                                    </Disclosure.Panel>
                                </>
                            )}
                        </Disclosure>
                    </div>
                )}

                <div
                    className="p2-new my-6 w-full cursor-pointer rounded-xl bg-white p-4 xl:hidden"
                    onClick={() => {
                        openModal('SEARCH_BY_SUBMISSION_NUMBER');
                    }}
                >
                    Search your form response by submission number
                </div>

                {!hasCustomDomain && (
                    <div className="shadow-powered-by mt-6 hidden w-full gap-2 rounded bg-white p-3 md:flex">
                        <span className="body3 text-black-700">Powered by:</span>
                        <Logo showProTag={false} isLink={false} isCustomDomain className="h-[14px] w-fit" />
                    </div>
                )}
            </div>
            <div className="flex-1 md:pl-12 !pb-4">
                <div className="flex space-x-1 border-b border-gray-200 overflow-x-auto pb-0">
                    {tabs.map((tab) => {
                        const isActive = pathname.includes(tab.path) || (tab.path === 'forms' && (pathname === basePath || pathname === `${basePath}/`));
                        return (
                            <Link
                                key={tab.path}
                                href={`${basePath}/${tab.path}`}
                                className={cn(
                                    'flex items-center gap-2 px-4 py-2 text-sm font-medium mb-[-1px] cursor-pointer hover:bg-black-200 hover:rounded whitespace-nowrap focus:outline-none',
                                    isActive
                                        ? 'border-b-2 border-black-900 text-black-900'
                                        : 'text-gray-500 hover:text-gray-700 hover:border-gray-300'
                                )}
                            >
                                {tab.icon}
                                {tab.title}
                            </Link>
                        );
                    })}
                </div>
                <div className="mt-4 flex gap-6 flex-col xl:flex-row">
                    {children}
                    <SearchBySubmissionNumber className='hidden xl:block' />
                </div>
            </div>
            <div className="lg:hidden">
                <PoweredBy />
            </div>
        </div>
    );
}

