'use client';

import cn from 'classnames';
import Link from 'next/link';
import { usePathname, useSearchParams } from 'next/navigation';
import React from 'react';
import { Trans } from 'react-i18next';

import { ChevronLeft, Eye, Shield as ShieldIcon, Trash2 } from 'lucide-react';

import AuthAccountProfileImage from '@app/components/auth/account-profile-image';
import RespondentDocumentLanguage from '@app/components/form/respondent-document-language';
import SiretoFooter from '@app/components/layout/sireto-footer';
import useRespondentLanguage from '@app/lib/hooks/use-respondent-language';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { utcToLocalDateIn, utcToLocalDateTimeIn } from '@app/utils/date-utils';
import { respondentLangQuery } from '@app/utils/respondent-lang-query';
import { deletionStatusLabel } from '@Components/workspace-client/workspace-form-response-deletion-card';
import RespondentFeedbackPanel from '@Components/form/respondent-feedback-panel';
import RespondentFeedbackSection from './respondent-feedback-section';
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
    const pathname = usePathname();
    // The page is in the respondent's language (and <html lang> says so); a
    // ?lang= from the link stays on every link out of it.
    const { t, language } = useRespondentLanguage();
    const langQuery = respondentLangQuery(useSearchParams()?.get('lang'));
    const portalBase = hasCustomDomain ? '' : workspaceName ? `/${workspaceName}` : '';

    const isSettings = pathname?.endsWith('/settings');
    const basePath = isSettings ? pathname.replace('/settings', '') : pathname?.replace('/form', '');

    const tabs = [
        {
            icon: <Eye className="h-5 w-5" aria-hidden="true" />,
            title: t('SUBMISSION.TAB_RESPONSE'),
            path: 'form'
        },
        {
            icon: <Trash2 className="h-5 w-5" aria-hidden="true" />,
            title: t('SUBMISSION.TAB_PRIVACY'),
            path: 'settings'
        }
    ];

    if (isLoading || isError || !data) {
        // Keep the workspace-branded shell while loading — swapping the whole
        // page for a white full-screen loader read as a flicker on every open.
        return (
            <div className="flex min-h-screen w-full flex-col bg-[#F5F7FB]!" aria-busy={isLoading || undefined}>
                <RespondentDocumentLanguage />
                <header className="border-b-black-300 sticky top-0 z-20 border-b bg-white">
                    <div className="mx-auto flex w-full max-w-[960px] items-center gap-2.5 px-5 py-3">
                        <AuthAccountProfileImage variant="circular" size={32} image={workspace?.profileImage} name={workspace?.title || workspaceName || 'W'} />
                        <span className="text-black-900 text-sm font-semibold">{workspace?.title || workspaceName}</span>
                    </div>
                </header>
                <div className="mx-auto mt-5 flex w-full max-w-[960px] flex-1 flex-col gap-4 px-5 pb-10">
                    <div className="bg-black-200 h-5 w-36 animate-pulse rounded" />
                    <div className="w-full rounded bg-white p-6">
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
        <div className="flex min-h-screen w-full flex-col bg-[#F5F7FB]!">
            <RespondentDocumentLanguage />
            <header className="border-b-black-300 sticky top-0 z-20 border-b bg-white">
                <Link href={`${portalBase}/forms${langQuery}`} className="mx-auto flex w-full max-w-[960px] items-center gap-2.5 px-5 py-3">
                    <AuthAccountProfileImage variant="circular" size={32} image={workspace?.profileImage} name={workspace?.title || workspaceName || 'W'} />
                    <span className="text-black-900 text-sm font-semibold">{workspace?.title || workspaceName}</span>
                </Link>
            </header>
            <main className="mx-auto mt-5 flex w-full max-w-[960px] flex-1 flex-col gap-4 px-5 pb-10">
                {/* Back to the list is navigation, so it is a link. */}
                <Link href={`${portalBase}/my-submissions${langQuery}`} className="text-black-700 hover:text-black-900 flex w-fit items-center gap-1 text-sm" lang={language}>
                    <ChevronLeft strokeWidth={2} width={18} height={18} aria-hidden="true" />
                    {t('PORTAL.MY_SUBMISSIONS')}
                </Link>

                {/* The receipt header: the same identity the list card shows,
                    so responders know they opened the right response. The
                    form's title is the page's one h1. */}
                <div className="w-full rounded bg-white p-6">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                        {form?.form?.title ? (
                            <h1 className="text-black-900 h3-new">{form.form.title}</h1>
                        ) : (
                            <h1 className="text-black-900 h3-new" lang={language}>
                                {t('PORTAL.UNTITLED_FORM')}
                            </h1>
                        )}
                        {response?.submissionUuid && (
                            <span className="bg-black-100 text-black-700 rounded px-2 py-0.5 font-mono text-xs" title={t('SUBMISSIONS.NUMBER_TITLE')}>
                                #{response.submissionUuid}
                            </span>
                        )}
                    </div>
                    <div className="text-black-600 mt-2 flex flex-wrap items-center gap-2 text-sm" lang={language}>
                        <span>{t('SUBMISSIONS.SUBMITTED', { date: utcToLocalDateTimeIn(response?.createdAt, language) })}</span>
                        {isAnonymous && (
                            <span className="flex items-center gap-1 rounded-full bg-[#E7F4EE] px-2 py-0.5 text-xs font-medium text-success-700" title={t('SUBMISSIONS.ANONYMOUS_TITLE')}>
                                <ShieldIcon className="h-3 w-3" strokeWidth={2} aria-hidden="true" />
                                {t('SUBMISSIONS.ANONYMOUS')}
                            </span>
                        )}
                        {!!response?.deletionStatus && (
                            <span className="rounded bg-brand-accent-100 px-2 py-0.5 text-xs font-medium text-brand-olive">{deletionStatusLabel(response.deletionStatus, response.declineReason, utcToLocalDateIn(response.updatedAt, language), t)}</span>
                        )}
                    </div>

                    {/* The organisation's updates on this submission: the
                        respondent's view, or the team's panel for members. */}
                    <RespondentFeedbackSection feedback={response?.feedback} workspaceTitle={workspace?.title} />
                    {form?.feedback && workspace?.id && (
                        <div className="mt-6">
                            <RespondentFeedbackPanel
                                key={response?.responseId}
                                workspaceId={workspace.id}
                                formId={form?.form?.formId}
                                responseId={response?.responseId}
                                feedback={form.feedback}
                                enabled={!!form?.form?.settings?.respondentFeedbackEnabled}
                                statuses={form?.form?.settings?.feedbackStatuses ?? []}
                            />
                        </div>
                    )}

                    <nav aria-label={t('SUBMISSION.TABS_LABEL')} className="border-b-black-300 mt-6 flex space-x-1 overflow-x-auto border-b pb-0" lang={language}>
                        {tabs.map((tab) => {
                            const isActive = pathname?.endsWith(`/${tab.path}`);
                            return (
                                <Link
                                    key={tab.path}
                                    href={`${basePath}/${tab.path}${langQuery}`}
                                    aria-current={isActive ? 'page' : undefined}
                                    className={cn(
                                        'mb-[-1px] flex cursor-pointer items-center gap-2 whitespace-nowrap border-b-2 px-4 py-2 text-sm font-medium focus:outline-hidden',
                                        isActive ? 'text-black-900 border-brand-500' : 'text-black-600 hover:text-black-900 border-transparent'
                                    )}
                                >
                                    {tab.icon}
                                    {tab.title}
                                </Link>
                            );
                        })}
                    </nav>

                    <div className="mt-6">
                        {children}
                    </div>
                </div>
                {/* Inside main, so every part of the page is in a landmark. */}
                {!hasCustomDomain && (
                    <div className="mt-auto flex flex-col items-center gap-2 pt-6">
                        <a href="https://bettercollected.com/" target="_blank" rel="noopener noreferrer" lang={language} className="text-black-600 hover:text-brand-600 text-center text-xs">
                            <Trans t={t} i18nKey="PORTAL.POWERED_BY" components={{ 1: <span className="font-semibold" /> }} />
                        </a>
                        <SiretoFooter language={language} />
                    </div>
                )}
            </main>
        </div>
    );
}
