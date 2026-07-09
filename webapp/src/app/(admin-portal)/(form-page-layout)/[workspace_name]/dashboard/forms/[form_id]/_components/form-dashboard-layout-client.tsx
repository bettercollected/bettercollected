'use client';

import cn from 'classnames';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import React, { useEffect, useMemo, useRef } from 'react';
import { useTranslation } from 'react-i18next';

import Divider from '@Components/common/divider';
import PrivateFormButtonWrapper from '@Components/common/private-form-button-wrapper';
import { Edit2, Play, Share2 } from 'lucide-react';

import { useModal } from '@app/components/modal-views/context';
import { useFullScreenModal } from '@app/components/modal-views/full-screen-modal-context';
import FullScreenLoader from '@app/components/ui/fullscreen-loader';
import { localesCommon } from '@app/constants/locales/common';
import { formConstant } from '@app/constants/locales/form';
import { formPage } from '@app/constants/locales/form-page';
import TopNavLayout from '@app/layouts/top-navbar-layout';
import { useBreakpoint, useIsMobile } from '@app/lib/hooks/use-breakpoint';
import { StandardFormDto } from '@app/models/dtos/form';
import { Button } from '@app/shadcn/components/ui/button';
import { resetSingleForm, selectForm, setForm } from '@app/store/forms/slice';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';
import getFormShareURL from '@app/utils/form-utils';
import { getEditFormURL } from '@app/utils/url-utils';
import { validateFormOpen } from '@app/utils/vvalidation-utils';
import PublishButton from '@app/views/molecules/form-builder/publish-button';

export default function FormDashboardLayoutClient({
    form,
    children,
    params
}: {
    form: StandardFormDto;
    children: React.ReactNode;
    params: { workspace_name: string; form_id: string }
}) {
    const { t } = useTranslation();
    const dispatch = useAppDispatch();
    const reduxStoreForm = useAppSelector(selectForm); // Check if this updates after dispatch(setForm(form))
    const breakpoint = useBreakpoint();
    const router = useRouter();
    const pathname = usePathname();
    const { openModal } = useModal();
    const { openModal: openFullScreenModal } = useFullScreenModal();
    const workspace = useAppSelector(selectWorkspace);
    const workspaceForm = useAppSelector(selectForm);

    const isMobile = useIsMobile();
    const isFormOpen = validateFormOpen(reduxStoreForm?.settings?.formCloseDate);

    // Initial load set form
    useEffect(() => {
        dispatch(setForm(form));
        return () => {
            dispatch(resetSingleForm());
        };
    }, [form, dispatch]);


    const storeForm = useAppSelector(selectForm);



    const tabMenu = useMemo(() => {
        // Five top-level destinations, all visible at once (the old 8-tab bar
        // silently overflowed and hid Form Link + Analytics). Deletion requests
        // live inside Responses as a segment; Visibility and Integrations are
        // Settings sections; /links is surfaced as "Share".
        const tabs: Array<{ title: string; path: string; count?: number; matches: string[] }> = [{ title: t(formConstant.preview), path: 'preview', matches: ['preview'] }];

        if (form?.isPublished) {
            tabs.push({
                title: 'Responses',
                path: 'responses',
                count: form.responses ?? 0,
                matches: ['responses', 'deletion-requests']
            });
            if (isFormOpen) {
                tabs.push({ title: 'Analytics', path: 'analytics', matches: ['analytics'] });
                tabs.push({ title: 'Share', path: 'links', matches: ['links'] });
            }
        }
        tabs.push({ title: t(localesCommon.settings), path: 'settings', matches: ['settings', 'visibility', 'integrations'] });
        return tabs;
    }, [form, t, isFormOpen]);

    const handleBackClick = () => {
        router.push(`/${workspace?.workspaceName}/dashboard/forms`);
    };

    const formTitle = form?.title?.trim() || 'Untitled form';

    // Keep the active tab visible: the tab bar scrolls horizontally when it
    // overflows, so center the current tab within its scroll container on
    // navigation (querying the container avoids relying on <Link> ref forwarding).
    const tabsContainerRef = useRef<HTMLDivElement | null>(null);
    useEffect(() => {
        // Defer to the next frame so tab widths are final before scrolling.
        const id = requestAnimationFrame(() => {
            const active = tabsContainerRef.current?.querySelector<HTMLElement>('[data-tab-active="true"]');
            active?.scrollIntoView({ inline: 'nearest', block: 'nearest' });
        });
        return () => cancelAnimationFrame(id);
    }, [pathname, tabMenu.length]);


    if (pathname.endsWith("/edit")) {
        return (
            <>{children}</>
        )
    }

    if (!form?.formId) {
        return <></>;
    }

    if (!storeForm?.formId) {
        return <FullScreenLoader />
    }

    return (
        <TopNavLayout isCustomDomain={false} isClientDomain={false} showNavbar={true} workspaceIdentity hideMenu={false} showAuthAccount={true} className="flex w-full flex-col !bg-white !p-0">
            <div className="my-2 w-full">
                <div className="mt-6 flex flex-col gap-1 sm:mt-12">
                    <FormPageLayer className="px-4 md:px-10 lg:px-28">
                        <div className="flex justify-between">
                            <div className="flex flex-col gap-1">
                                <nav aria-label="Breadcrumb" className="text-black-600 flex w-fit items-center gap-1.5 text-[13px]">
                                    <button type="button" onClick={handleBackClick} className="hover:text-black-900 hover:underline">
                                        Forms
                                    </button>
                                    <span className="text-black-400">/</span>
                                    <span className="text-black-800 max-w-[320px] truncate font-medium">{formTitle}</span>
                                </nav>
                                {isMobile ? <h1 className="hp3-new">{formTitle}</h1> : <h1 className="h2-new">{formTitle}</h1>}
                            </div>
                            <div className="hidden gap-4 lg:flex">
                                {form?.settings?.provider === 'self' && form?.builderVersion === 'v2' && (
                                    <Button
                                        icon={<Edit2 className="h-5 w-5" />}
                                        variant="v2Button"
                                        className="!px-0 sm:!px-5"
                                        onClick={() => {
                                            router.push(getEditFormURL(workspace, form));
                                        }}
                                    >
                                        <span className="hidden sm:block">{t(formPage.editForm)}</span>
                                    </Button>
                                )}
                                {form?.isPublished && isFormOpen && (
                                    <PrivateFormButtonWrapper isPrivate={workspaceForm?.settings?.hidden}>
                                        <Button
                                            variant="primary"
                                            icon={<Share2 className="h-5 w-5" />}
                                            className="!bg-[#2456CC] hover:!bg-[#1E49AD] !px-0 text-white sm:!px-5"
                                            disabled={workspaceForm?.settings?.hidden}
                                            onClick={() =>
                                                openModal('SHARE_VIEW', {
                                                    url: getFormShareURL(workspaceForm, workspace),
                                                    title: t(formConstant.shareThisForm)
                                                })
                                            }
                                        >
                                            <span className="hidden sm:block">{t(formPage.shareForm)}</span>
                                        </Button>
                                    </PrivateFormButtonWrapper>
                                )}
                            </div>
                            <div className="flex gap-2 lg:hidden">
                                {form.builderVersion === 'v2' && (
                                    <Button
                                        icon={<Play className="h-5 w-5" />}
                                        onClick={() => {
                                            openFullScreenModal('PREVIEW_MODAL');
                                        }}
                                        className="text-[10px]"
                                        variant={'v2Button'}
                                    >
                                        Preview
                                    </Button>
                                )}

                                {form?.isPublished ? (
                                    <PrivateFormButtonWrapper isPrivate={workspaceForm?.settings?.hidden}>
                                        <Button
                                            variant={'primary'}
                                            icon={<Share2 className="h-5 w-5" />}
                                            disabled={workspaceForm?.settings?.hidden}
                                            onClick={() =>
                                                openModal('SHARE_VIEW', {
                                                    url: getFormShareURL(workspaceForm, workspace),
                                                    title: t(formConstant.shareThisForm)
                                                })
                                            }
                                        >
                                            <span className="">{'Share'}</span>
                                        </Button>
                                    </PrivateFormButtonWrapper>
                                ) : (
                                    <PublishButton refresh />
                                )}
                            </div>
                        </div>
                        {!isMobile && (
                            <div className="text-black-700 mb-4 mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-[13px]">
                                {form?.isPublished ? (
                                    <span className="rounded-full bg-[#E7F4EE] px-2 py-0.5 text-xs font-semibold text-[#0E8A5F]">Published</span>
                                ) : (
                                    <span className="bg-black-200 text-black-700 rounded-full px-2 py-0.5 text-xs font-semibold">Draft</span>
                                )}
                                <span className="tabular-nums">{form?.responses ?? 0} responses</span>
                                <span className="text-black-400">·</span>
                                <span>{formProvenance(form)}</span>
                            </div>
                        )}
                        <Divider className="mt-6 hidden md:flex" />
                    </FormPageLayer>
                    <div className="md:px-10 lg:px-28 pt-4">
                        <div ref={tabsContainerRef} className="flex space-x-1 border-b border-gray-200 overflow-x-auto">
                            {tabMenu.map((tab) => {
                                const isActive = tab.matches.some((m) => pathname?.includes(`/${m}`));
                                return (
                                    <Link key={tab.path} data-tab-active={isActive} href={`/${params.workspace_name}/dashboard/forms/${params.form_id}/${tab.path}`} className={cn(
                                        'flex items-center gap-1.5 whitespace-nowrap border-b-2 px-4 py-2.5 text-sm',
                                        isActive
                                            ? 'border-[#2456CC] text-black-900 font-semibold'
                                            : 'text-black-600 hover:text-black-900 border-transparent font-medium'
                                    )}>
                                        {tab.title}
                                        {typeof tab.count === 'number' && <span className="bg-black-200 text-black-700 rounded-full px-2 py-0.5 text-xs font-medium tabular-nums">{tab.count}</span>}
                                    </Link>
                                );
                            })}
                        </div>
                    </div>
                    <div className="w-full pt-5">
                        {children}
                    </div>
                    {form?.isPublished && (
                        <div className="border-black-200 text-black-600 mx-4 mt-16 flex flex-wrap items-center justify-center gap-x-2 gap-y-1 border-t py-4 text-[13px] md:mx-10 lg:mx-28">
                            {typeof (form as any)?.version === 'number' && <span>Version {(form as any).version}</span>}
                            {typeof (form as any)?.version === 'number' && <span className="text-black-400">·</span>}
                            <a href={getFormShareURL(workspaceForm ?? form, workspace)} target="_blank" rel="noopener noreferrer" className="hover:text-black-900 underline decoration-dotted underline-offset-2">
                                Open form ↗
                            </a>
                        </div>
                    )}
                </div>
            </div>
        </TopNavLayout>
    );
}

const FormPageLayer = ({ children, className }: any) => {
    return <div className={className}>{children}</div>;
};

/** Plain-words provenance for the header meta line. */
function formProvenance(form: StandardFormDto): string {
    const provider = form?.settings?.provider;
    if (provider === 'google') return 'Imported from Google Forms';
    if (provider === 'typeform') return 'Imported from Typeform';
    return 'bettercollected form';
}
