'use client';

import cn from 'classnames';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import React from 'react';

import { ChevronLeft, Eye, Shield as ShieldIcon, Trash2 } from 'lucide-react';

import AuthAccountProfileImage from '@app/components/auth/account-profile-image';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { utcToLocalDateTIme } from '@app/utils/date-utils';
import { useSubmissionContext } from './submission-context';

/**
 * The submission detail is part of the responder portal journey (receipt →
 * response → deletion), so it wears the same clothes: surface wash, white
 * cards, receipt identity (number · time · anonymous), portal tab treatment.
 * It used to be a bare white page with its own tab style — responders landed
 * on what looked like a different product right when they were exercising
 * their data rights.
 */
export default function SubmissionLayoutClient({ children }: { children: React.ReactNode }) {
    const { data, isLoading, isError, hasCustomDomain, workspaceName } = useSubmissionContext();
    const workspace = useAppSelector(selectWorkspace);
    const form: any = data ?? {};
    const router = useRouter();
    const pathname = usePathname();
    const portalBase = hasCustomDomain ? '' : `/${workspaceName ?? ''}`;

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

    const tabs = [
        {
            icon: <Eye className="h-5 w-5" />,
            title: 'My response',
            path: 'form'
        },
        {
            icon: <Trash2 className="h-5 w-5" />,
            title: 'Privacy & deletion',
            path: 'settings'
        }
    ];

    if (isLoading || isError || !data) {
        // Keep the workspace-branded shell while loading — swapping the whole
        // page for a white full-screen loader read as a flicker on every open.
        return (
            <div className="flex min-h-screen w-full flex-col !bg-[#F6F8FC]">
                <header className="border-b-black-200 sticky top-0 z-20 border-b bg-white">
                    <div className="mx-auto flex w-full max-w-[960px] items-center gap-2.5 px-5 py-3">
                        <AuthAccountProfileImage variant="circular" size={32} image={workspace?.profileImage} name={workspace?.title || workspaceName || 'W'} />
                        <span className="text-black-900 text-sm font-semibold">{workspace?.title || workspaceName}</span>
                    </div>
                </header>
                <div className="mx-auto mt-5 flex w-full max-w-[960px] flex-1 flex-col gap-4 px-5 pb-10">
                    <div className="bg-black-200 h-5 w-36 animate-pulse rounded" />
                    <div className="w-full rounded-xl bg-white p-6">
                        <div className="bg-black-100 h-7 w-64 animate-pulse rounded" />
                        <div className="bg-black-100 mt-3 h-4 w-80 animate-pulse rounded" />
                        <div className="bg-black-100 mt-8 h-40 w-full animate-pulse rounded" />
                    </div>
                </div>
            </div>
        );
    }

    const response = form?.response ?? {};
    const isAnonymous = !response?.dataOwnerIdentifier;

    return (
        // This page belongs to the WORKSPACE's branded space (possibly their
        // custom domain). The platform wordmark up top read as a jarring brand
        // switch mid-journey — the workspace's own identity leads instead, and
        // bettercollected stays where the portal keeps it: a quiet caption.
        <div className="flex min-h-screen w-full flex-col !bg-[#F6F8FC]">
            <header className="border-b-black-200 sticky top-0 z-20 border-b bg-white">
                <Link href={`${portalBase}/forms`} className="mx-auto flex w-full max-w-[960px] items-center gap-2.5 px-5 py-3">
                    <AuthAccountProfileImage variant="circular" size={32} image={workspace?.profileImage} name={workspace?.title || workspaceName || 'W'} />
                    <span className="text-black-900 text-sm font-semibold">{workspace?.title || workspaceName}</span>
                </Link>
            </header>
            <div className="mx-auto mt-5 flex w-full max-w-[960px] flex-1 flex-col gap-4 px-5 pb-10">
                <button type="button" className="text-black-700 hover:text-black-900 flex w-fit items-center gap-1 text-sm" onClick={goToSubmissions}>
                    <ChevronLeft strokeWidth={2} width={18} height={18} />
                    My submissions
                </button>

                {/* The receipt header: the same identity the list card shows,
                    so responders know they opened the right response. */}
                <div className="w-full rounded-xl bg-white p-6">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                        <span className="text-black-900 h3-new">{form?.form?.title || 'Untitled Form'}</span>
                        {response?.submissionUuid && (
                            <span className="bg-black-100 text-black-700 rounded px-2 py-0.5 font-mono text-xs" title="Your submission number — you can also search by it">
                                #{response.submissionUuid}
                            </span>
                        )}
                    </div>
                    <div className="text-black-600 mt-2 flex flex-wrap items-center gap-2 text-sm">
                        <span>Submitted: {utcToLocalDateTIme(response?.createdAt)}</span>
                        {isAnonymous && (
                            <span className="flex items-center gap-1 rounded-full bg-[#E7F4EE] px-2 py-0.5 text-xs font-medium text-[#0E8A5F]" title="Submitted without your identity attached">
                                <ShieldIcon className="h-3 w-3" strokeWidth={2} />
                                Anonymous
                            </span>
                        )}
                        {!!response?.deletionStatus && <span className="rounded bg-[#FBF3E4] px-2 py-0.5 text-xs font-medium text-[#B26B00]">Deletion requested</span>}
                    </div>

                    <div className="border-b-black-200 mt-6 flex space-x-1 overflow-x-auto border-b pb-0">
                        {tabs.map((tab) => {
                            const isActive = pathname?.endsWith(`/${tab.path}`);
                            return (
                                <Link
                                    key={tab.path}
                                    href={`${basePath}/${tab.path}`}
                                    className={cn(
                                        'mb-[-1px] flex cursor-pointer items-center gap-2 whitespace-nowrap border-b-2 px-4 py-2 text-sm font-medium focus:outline-none',
                                        isActive ? 'text-black-900 border-[#2456CC]' : 'text-black-600 hover:text-black-900 border-transparent'
                                    )}
                                >
                                    {tab.icon}
                                    {tab.title}
                                </Link>
                            );
                        })}
                    </div>

                    <div className="mt-6">
                        {children}
                    </div>
                </div>
            </div>
            {!hasCustomDomain && (
                <a href="https://bettercollected.com/" target="_blank" rel="noopener noreferrer" className="text-black-500 hover:text-black-700 mx-auto pb-6 text-center text-xs">
                    Powered by <span className="font-semibold">bettercollected</span>
                </a>
            )}
        </div>
    );
}
