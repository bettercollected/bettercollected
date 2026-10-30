'use client';

import React, { useEffect, useId, useMemo, useRef, useState } from 'react';

import Link from 'next/link';

import BetterCollectedLogo from '@Components/icons/bettercollected-logo';
import { ChevronRight, KeyRound, Plus } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import AuthAccountProfileImage from '@app/components/auth/account-profile-image';
import { useModal } from '@app/components/modal-views/context';
import environments from '@app/configs/environments';
import { workspaceSelect } from '@app/constants/locales/workspace-select';
import { navigateWithReferrer } from '@app/lib/sso';
import { NO_ACCESS_NOTICE, SEARCH_THRESHOLD, WorkspaceChoice, WorkspaceSelection, matchesSearch, orderChoices, readLastWorkspaceId, rememberWorkspace, workspaceHome } from '@app/lib/workspace-selection';
import { buttonClassName } from '@app/shadcn/components/ui/button';
import { Input } from '@app/shadcn/components/ui/input';
import { cn } from '@app/shadcn/util/lib';
import { selectAuth } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';
import { useGetWorkspaceSelectionQuery } from '@app/store/workspaces/api';

const KNOWN_ROLES = new Set(['OWNER', 'ADMIN', 'EDITOR', 'REVIEWER', 'VIEWER', 'PRIVACY_OFFICER']);

const rowClassName = 'group flex w-full items-center gap-3 rounded-xl border border-black-300 bg-white px-4 py-3 text-left transition-colors hover:border-brand-400 hover:bg-brand-100/40 focus-visible:border-brand-500';

interface WorkspaceSelectViewProps {
    /** a fixed notice code from the URL (only `no_access` is shown) */
    notice?: string | null;
}

/**
 * The workspace selection screen after sign-in, and the switcher's "Choose
 * workspace". Every row comes from the server's list of what the user may
 * open; the last-used workspace (a local id) only moves its row to the top.
 */
export default function WorkspaceSelectView({ notice }: WorkspaceSelectViewProps) {
    const { t } = useTranslation();
    const { data, isLoading, isError, refetch } = useGetWorkspaceSelectionQuery();
    const auth = useAppSelector(selectAuth);
    const { openModal } = useModal();
    const headingRef = useRef<HTMLHeadingElement>(null);
    const [query, setQuery] = useState('');
    // the rows come from the client-side query, so no server render shows this order
    const [lastUsedId] = useState<string | null>(() => readLastWorkspaceId());
    const searchId = useId();

    useEffect(() => {
        headingRef.current?.focus();
    }, []);

    const ordered = useMemo(() => orderChoices(data?.workspaces ?? [], lastUsedId), [data, lastUsedId]);
    const showSearch = ordered.length > SEARCH_THRESHOLD;
    const visible = showSearch ? ordered.filter((choice) => matchesSearch(choice, query)) : ordered;
    const markedLastUsed = ordered.length > 1 && ordered[0]?.id === lastUsedId ? lastUsedId : null;

    return (
        <div className="min-h-screen w-full bg-black-100">
            <div className="mx-auto flex min-h-screen w-full max-w-[600px] flex-col px-4 py-8 sm:px-6 sm:py-12">
                <div className="mb-8">
                    <BetterCollectedLogo className="h-[19px] w-auto" />
                </div>

                <main className="flex flex-1 flex-col" aria-busy={isLoading}>
                    <h1 ref={headingRef} tabIndex={-1} className="text-2xl leading-tight font-semibold tracking-tight text-black-900 outline-hidden sm:text-[28px]">
                        {t(workspaceSelect.title)}
                    </h1>
                    <p className="mt-2 text-[15px] leading-relaxed text-black-700">{t(workspaceSelect.description)}</p>

                    {notice === NO_ACCESS_NOTICE && (
                        <p role="status" className="mt-5 rounded-lg border border-[#F0D9B5] bg-[#FDF8EF] px-4 py-3 text-sm text-black-800">
                            {t(workspaceSelect.noAccess)}
                        </p>
                    )}

                    <div className="mt-6">
                        {isLoading ? (
                            <SkeletonRows />
                        ) : isError || !data ? (
                            <div role="alert" className="flex flex-col items-start gap-3 rounded-xl border border-black-300 bg-white px-4 py-4">
                                <p className="text-sm text-black-800">{t(workspaceSelect.loadFailed)}</p>
                                <button type="button" className={buttonClassName({ variant: 'tertiary', size: 'sm' })} onClick={() => refetch()}>
                                    {t(workspaceSelect.retry)}
                                </button>
                            </div>
                        ) : ordered.length === 0 ? (
                            <EmptyState selection={data} />
                        ) : (
                            <>
                                {showSearch && (
                                    <div className="mb-4">
                                        <label htmlFor={searchId} className="mb-1.5 block text-sm font-medium text-black-800">
                                            {t(workspaceSelect.searchLabel)}
                                        </label>
                                        <Input id={searchId} type="search" value={query} placeholder={t(workspaceSelect.searchPlaceholder)} onChange={(e) => setQuery(e.target.value)} autoComplete="off" />
                                    </div>
                                )}
                                <p className="mb-2 text-xs font-medium tracking-wider text-black-600 uppercase" aria-hidden="true">
                                    {t(workspaceSelect.count, { count: ordered.length })}
                                </p>
                                {visible.length === 0 ? (
                                    <p role="status" className="rounded-xl border border-dashed border-black-400 px-4 py-6 text-center text-sm text-black-700">
                                        {t(workspaceSelect.noMatch, { query: query.trim() })}
                                    </p>
                                ) : (
                                    <ul aria-label={t(workspaceSelect.listLabel)} className="flex flex-col gap-2">
                                        {visible.map((choice) => (
                                            <li key={choice.id}>
                                                <WorkspaceRow choice={choice} lastUsed={choice.id === markedLastUsed} email={auth?.email} />
                                            </li>
                                        ))}
                                    </ul>
                                )}
                            </>
                        )}
                    </div>
                </main>

                {auth?.email && (
                    <footer className="mt-10 flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-black-600">
                        <span className="min-w-0 break-all">{t(workspaceSelect.signedInAs, { email: auth.email })}</span>
                        <span aria-hidden="true">·</span>
                        <button type="button" className="text-brand-600 underline underline-offset-2 hover:text-brand-700" onClick={() => openModal('LOGOUT_VIEW', {})}>
                            {t(workspaceSelect.signOut)}
                        </button>
                    </footer>
                )}
            </div>
        </div>
    );
}

function WorkspaceRow({ choice, lastUsed, email }: { choice: WorkspaceChoice; lastUsed: boolean; email?: string }) {
    const { t } = useTranslation();
    const title = choice.title?.trim() || choice.workspaceName;
    const role = choice.role && KNOWN_ROLES.has(choice.role) ? t(`WORKSPACE_ROLES.${choice.role}.NAME`) : null;

    const body = (
        <>
            <AuthAccountProfileImage size={40} image={choice.profileImage ?? undefined} name={title} variant="rounded" className="shrink-0" />
            <span className="flex min-w-0 flex-1 flex-col gap-0.5">
                <span className="truncate text-[15px] font-semibold text-black-900">{title}</span>
                <span className="flex min-w-0 flex-wrap items-center gap-x-1.5 text-[13px] text-black-700">
                    {role && <span>{role}</span>}
                    {role && choice.customDomain && <span aria-hidden="true">·</span>}
                    {choice.customDomain && <span className="truncate">{choice.customDomain}</span>}
                </span>
                {(lastUsed || choice.disabled || choice.ssoRequired) && (
                    <span className="mt-1 flex flex-wrap gap-1.5">
                        {lastUsed && <Badge className="bg-brand-100 text-brand-600">{t(workspaceSelect.lastUsed)}</Badge>}
                        {choice.disabled && <Badge className="bg-black-200 text-black-800">{t(workspaceSelect.readOnly)}</Badge>}
                        {choice.ssoRequired && (
                            <Badge className="bg-[#FDF3E3] text-[#7A4B0B]">
                                <KeyRound className="h-3 w-3" aria-hidden="true" />
                                {t(workspaceSelect.ssoRequired)}
                            </Badge>
                        )}
                    </span>
                )}
            </span>
            {/* on a phone the badge says it; the action text would crowd the row */}
            {choice.ssoRequired && <span className="hidden shrink-0 text-sm font-medium text-brand-600 sm:inline">{t(workspaceSelect.ssoAction)}</span>}
            {choice.ssoRequired && <span className="sr-only sm:hidden">{t(workspaceSelect.ssoAction)}</span>}
            <ChevronRight className={cn('h-5 w-5 shrink-0 text-black-500 group-hover:text-brand-500', choice.ssoRequired && 'sm:hidden')} aria-hidden="true" />
        </>
    );

    if (choice.ssoRequired) {
        // no way in through this session: start the workspace's SSO sign-in,
        // which comes back to this workspace (docs/sso.md)
        return (
            <button
                type="button"
                className={rowClassName}
                onClick={() => {
                    rememberWorkspace(choice.id);
                    navigateWithReferrer(`${environments.API_ENDPOINT_HOST}/auth/sso/login?${new URLSearchParams({ email: email ?? '' }).toString()}`);
                }}
            >
                {body}
            </button>
        );
    }

    return (
        <Link href={workspaceHome(choice)} className={rowClassName} onClick={() => rememberWorkspace(choice.id)}>
            {body}
        </Link>
    );
}

function Badge({ className, children }: { className?: string; children: React.ReactNode }) {
    return <span className={cn('inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium', className)}>{children}</span>;
}

function EmptyState({ selection }: { selection: WorkspaceSelection }) {
    const { t } = useTranslation();
    const message = !selection.isCreator ? workspaceSelect.emptyRespondent : selection.canCreateWorkspace ? workspaceSelect.emptyCreate : workspaceSelect.emptyAsk;
    return (
        <section aria-labelledby="workspace-select-empty" className="rounded-xl border border-black-300 bg-white px-5 py-6">
            <h2 id="workspace-select-empty" className="text-lg font-semibold text-black-900">
                {t(workspaceSelect.emptyTitle)}
            </h2>
            <p className="mt-2 text-[15px] leading-relaxed text-black-700">{t(message)}</p>
            {selection.isCreator && selection.canCreateWorkspace && (
                <Link href="/workspace/create" className={buttonClassName({ variant: 'primary', size: 'medium', className: 'mt-5 inline-flex gap-2' })}>
                    <Plus className="h-4 w-4" aria-hidden="true" />
                    {t(workspaceSelect.create)}
                </Link>
            )}
        </section>
    );
}

function SkeletonRows() {
    return (
        <div className="flex flex-col gap-2" aria-hidden="true">
            {[0, 1, 2].map((i) => (
                <div key={i} className="flex items-center gap-3 rounded-xl border border-black-300 bg-white px-4 py-3">
                    <div className="h-10 w-10 animate-pulse rounded-md bg-black-200" />
                    <div className="flex flex-1 flex-col gap-2">
                        <div className="h-3.5 w-1/3 animate-pulse rounded bg-black-200" />
                        <div className="h-3 w-1/5 animate-pulse rounded bg-black-200" />
                    </div>
                </div>
            ))}
        </div>
    );
}
