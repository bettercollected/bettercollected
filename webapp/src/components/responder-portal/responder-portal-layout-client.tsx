'use client';

import cn from 'classnames';
import Link from 'next/link';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import React, { useEffect, useRef, useState } from 'react';
import { Trans, useTranslation } from 'react-i18next';

import Divider from '@Components/common/divider';
import { Button } from '@app/shadcn/components/ui/button';
import { Disclosure } from '@headlessui/react';

import { FormIcon } from '@Components/icons/form-icon';
import WorkspaceDetailsCard from '@Components/responder-portal/workspace-details-card';
import AuthAccountProfileImage from '@app/components/auth/account-profile-image';
import { ChevronDown } from '@app/components/icons/chevron-down';
import { HistoryIcon } from '@app/components/icons/history';
import { Logout } from '@app/components/icons/logout-icon';
import { TrashIcon } from '@app/components/icons/trash';
import { useModal } from '@app/components/modal-views/context';
import ActiveLink from '@app/components/ui/links/active-link';
import RespondentDocumentLanguage from '@app/components/form/respondent-document-language';
import SiretoFooter from '@app/components/layout/sireto-footer';
import PoweredBy from '@app/components/ui/powered-by';
import { profileMenu } from '@app/constants/locales/profile-menu';
import { selectAuth } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';
import useRespondentLanguage from '@app/lib/hooks/use-respondent-language';
import { respondentLangQuery } from '@app/utils/respondent-lang-query';
import { getFullNameFromUser } from '@app/utils/user-utils';
import SearchBySubmissionNumber from './search-by-submission-number';

export default function ResponderPortalLayoutClient({
    children,
    hasCustomDomain
}: {
    children: React.ReactNode;
    hasCustomDomain: boolean;
}) {
    const { t } = useTranslation();
    // The tab names are in the respondent's language (and marked so).
    const { t: tRespondent, language } = useRespondentLanguage();
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
            title: tRespondent('PORTAL.FORMS'),
            path: 'forms'
        },
        {
            icon: <HistoryIcon className="w-5 h-5" />,
            title: tRespondent('PORTAL.MY_SUBMISSIONS'),
            path: 'my-submissions'
        }
    ];

    if (auth.id) {
        tabs.push({
            icon: <TrashIcon className="w-5 h-5" />,
            title: tRespondent('PORTAL.DELETION_REQUESTS'),
            path: 'deletion-requests'
        });
    }

    const basePath = hasCustomDomain ? '' : `/${workspace.workspaceName}`;
    // A ?lang=nl|en from the link stays on the tab links, so the next page
    // (and a reload of it) is in the same language.
    const langQuery = respondentLangQuery(useSearchParams()?.get('lang'));

    // The tabs wrap onto a second line instead of scrolling, so every tab,
    // including deletion requests, is visible whatever the language's label
    // lengths. Each tab carries its own bottom rule so a wrapped line keeps
    // the underline. Should a single tab ever be wider than the bar, it
    // scrolls, and a fade at the edge with more tabs past it says so.
    const tabBar = useRef<HTMLDivElement>(null);
    const [moreTabs, setMoreTabs] = useState({ before: false, after: false });
    useEffect(() => {
        const bar = tabBar.current;
        if (!bar) return;
        const update = () => setMoreTabs({ before: bar.scrollLeft > 1, after: bar.scrollLeft + bar.clientWidth < bar.scrollWidth - 1 });
        update();
        bar.addEventListener('scroll', update, { passive: true });
        window.addEventListener('resize', update);
        return () => {
            bar.removeEventListener('scroll', update);
            window.removeEventListener('resize', update);
        };
    }, [tabs.length, language]);

    return (
        // Desktop: the page itself doesn't scroll — the sidebars are short, so
        // only the central content column scrolls, the tab bar stays affixed,
        // and a stable scrollbar gutter stops the layout flicker that used to
        // happen the moment content grew past a screenful.
        // The whole page is its main content (the workspace's identity, how to
        // find your submissions, the tabs), so every part is in a landmark.
        <main className={`max-w-screen bg-[#F5F7FB]! flex h-screen max-h-screen w-screen flex-col overflow-auto p-5 opacity-100 md:flex-row md:overflow-hidden md:p-10 ${!hasCustomDomain ? 'pb-20!' : ''}`}>
            {/* The portal is in the respondent's language (<html lang>), as the form pages are. */}
            <RespondentDocumentLanguage />
            <div className="max-w-screen w-full md:max-h-full md:w-[320px] md:max-w-[320px] md:overflow-y-auto">
                <WorkspaceDetailsCard workspace={workspace} audience="respondent" />
                {!auth.id && !auth.isLoading && (
                    <div className="mt-6 flex flex-col rounded bg-white p-6" lang={language}>
                        <h2 className="h4-new">{tRespondent('PORTAL.SIGN_IN_TITLE')}</h2>
                        <p className="p2-new text-black-600 mt-2">{tRespondent('PORTAL.SIGN_IN_TEXT')}</p>
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
                            {tRespondent('PORTAL.VERIFY_EMAIL')}
                        </Button>
                        <p className="p4-new text-black-600 mt-3">{tRespondent('PORTAL.ANONYMOUS_HINT')}</p>
                    </div>
                )}
                {auth.id && (
                    <div className="mt-6 w-full  rounded bg-white ">
                        <Disclosure>
                            {({ open }) => (
                                <>
                                    <Disclosure.Button className="flex w-full cursor-pointer items-center justify-between gap-2 p-4">
                                        <div className="flex gap-2">
                                            <AuthAccountProfileImage size={36} image={auth?.profileImage} name={getFullNameFromUser(auth) ?? ''} />
                                            <div className="text-black-700! flex flex-col justify-center gap-2 pr-1 text-start">
                                                <span className="body6 leading-none!">{getFullNameFromUser(auth)?.trim() || auth?.email || ''}</span>
                                                {/* Only repeat the email when the first line is a real name. */}
                                                {!!getFullNameFromUser(auth)?.trim() && getFullNameFromUser(auth)?.trim() !== auth?.email && <span className="body5 leading-none!">{auth?.email} </span>}
                                            </div>
                                        </div>
                                        <ChevronDown className={`${open ? 'rotate-180 transform' : ''} h-3 w-3 text-blue-900`} />
                                    </Disclosure.Button>
                                    <Disclosure.Panel className="pb-2">
                                        {!auth?.roles?.includes('FORM_CREATOR') && (
                                            <>
                                                <Divider className="text-black-200" />
                                                <div className="p4-new text-black-600 p-4" lang={language}>
                                                    {tRespondent('PORTAL.NO_WORKSPACE')}{' '}
                                                    <ActiveLink target="_blank" href="https://bettercollected.com" className="text-blue-500">
                                                        {tRespondent('PORTAL.TRY_PRODUCT')}
                                                    </ActiveLink>
                                                </div>
                                            </>
                                        )}
                                        <Divider className="text-black-200" />
                                        {/* A real button, so signing out works from the keyboard too. */}
                                        <button type="button" className="text-black-600 hover:bg-brand-100 m-2 flex w-[calc(100%-1rem)] cursor-pointer gap-2 rounded p-2 text-left active:bg-blue-100" onClick={handleLogout}>
                                            <Logout width={24} height={24} aria-hidden="true" />
                                            <span>{t(profileMenu.logout)}</span>
                                        </button>
                                    </Disclosure.Panel>
                                </>
                            )}
                        </Disclosure>
                    </div>
                )}

                {/* The receipt search lives with the other identity/recovery
                    tools in the sidebar — one utility column, two-column page. */}
                <SearchBySubmissionNumber className="mt-6 w-full" />

                {/* Attribution, not advertisement: a quiet caption, not a card
                    competing with the workspace's own identity. */}
                {!hasCustomDomain && (
                    <>
                        <a href="https://bettercollected.com/" target="_blank" rel="noopener noreferrer" lang={language} className="text-black-600 hover:text-brand-600 mt-6 hidden w-full justify-center gap-1 text-xs md:flex">
                            <Trans t={tRespondent} i18nKey="PORTAL.POWERED_BY" components={{ 1: <span className="font-semibold" /> }} />
                        </a>
                        <SiretoFooter className="mt-2 hidden md:block" language={language} />
                    </>
                )}
            </div>
            <div className="flex flex-1 flex-col pb-4! md:min-h-0 md:min-w-0 md:pl-12">
                <div className="relative">
                    <div ref={tabBar} className="flex flex-wrap gap-x-1 border-b border-black-400 overflow-x-auto pb-0" lang={language}>
                        {tabs.map((tab) => {
                            const isActive = pathname.includes(tab.path) || (tab.path === 'forms' && (pathname === basePath || pathname === `${basePath}/`));
                            return (
                                <Link
                                    key={tab.path}
                                    href={`${basePath}/${tab.path}${langQuery}`}
                                    aria-current={isActive ? 'page' : undefined}
                                    className={cn(
                                        'flex items-center gap-2 px-4 py-2 text-sm font-medium mb-[-1px] cursor-pointer hover:bg-black-200 hover:rounded whitespace-nowrap focus:outline-hidden',
                                        isActive
                                            ? 'text-black-900 border-b-2 border-brand-500'
                                            : 'text-black-600 border-b border-black-400 hover:text-black-900 hover:border-black-300'
                                    )}
                                >
                                    {tab.icon}
                                    {tab.title}
                                </Link>
                            );
                        })}
                    </div>
                    {moreTabs.before && <div aria-hidden="true" data-testid="more-tabs-before" className="pointer-events-none absolute inset-y-0 left-0 w-10 bg-linear-to-r from-[#F5F7FB] to-transparent" />}
                    {moreTabs.after && <div aria-hidden="true" data-testid="more-tabs-after" className="pointer-events-none absolute inset-y-0 right-0 w-10 bg-linear-to-l from-[#F5F7FB] to-transparent" />}
                </div>
                <div className="mt-4 flex flex-col gap-6 md:min-h-0 md:flex-1">
                    {/* Only the content column scrolls; the sidebar column
                        (identity + receipt search) stays put. */}
                    <div className="min-w-0 flex-1 md:min-h-0 md:overflow-y-auto md:scrollbar-gutter-stable">{children}</div>
                </div>
            </div>
            {!hasCustomDomain && <SiretoFooter className="mt-6 md:hidden" language={language} />}
            <div className="lg:hidden">
                <PoweredBy language={language} />
            </div>
        </main>
    );
}

