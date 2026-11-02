'use client';

import React, { useMemo } from 'react';

import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';

import PrivateFormButtonWrapper from '@Components/common/private-form-button-wrapper';
import { ArrowLeft, BarChart3, Edit2, History, Inbox, LayoutGrid, type LucideIcon, Play, Settings, Share2, Trash2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import FormOptionsDropdownMenu from '@app/components/datatable/form-options-dropdown';
import { SETTINGS_PAGE_ICONS, SETTINGS_PAGE_LABELS, settingsPages } from '@app/components/form/settings-pages';
import { useModal } from '@app/components/modal-views/context';
import { useFullScreenModal } from '@app/components/modal-views/full-screen-modal-context';
import { buttonConstant } from '@app/constants/locales/button';
import { localesCommon } from '@app/constants/locales/common';
import { formConstant } from '@app/constants/locales/form';
import { useIsPhone } from '@app/lib/hooks/use-breakpoint';
import { useWorkspacePermissions } from '@app/lib/hooks/use-workspace-permissions';
import { StandardFormDto } from '@app/models/dtos/form';
import { WorkspacePermission } from '@app/models/enums/workspace-permission';
import { Button } from '@app/shadcn/components/ui/button';
import { cn } from '@app/shadcn/util/lib';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';
import getFormShareURL from '@app/utils/form-utils';
import { getEditFormURL } from '@app/utils/url-utils';
import { validateFormOpen } from '@app/utils/vvalidation-utils';
import PublishButton from '@app/views/molecules/form-builder/publish-button';

/* ------------------------------------------------------------- the model */

export interface FormNavItem {
    key: string;
    label: string;
    href: string;
    icon: LucideIcon;
    /** Shown as a badge next to the label (the number of responses). */
    count?: number;
    /** On this section's page (Responses is also active on Deletion requests). */
    active: boolean;
    /** Sub-pages of a section (Deletion requests under Responses, the Settings pages). */
    children?: FormNavItem[];
    /** The side menu lists the sub-pages only while the section is open (Settings); the phone sheet always lists them. */
    opensInPlace?: boolean;
}

interface NavInput {
    form: StandardFormDto;
    base: string;
    pathname: string;
    can: (permission: WorkspacePermission) => boolean;
    formRevisionsUiEnabled: boolean;
    t: (key: string) => string;
}

/**
 * The sections of a form, in order, for the person looking at it. Who sees what
 * is what the tab row decided before: Pages always; for a published form
 * Responses (response.read) with Deletion requests under it (privacy.manage;
 * privacy.manage alone gets Deletion requests as a section of its own),
 * Analytics and Share while the form is open, Versions (server flag, form.read);
 * Settings for form.edit, with the pages that form has (`settingsPages`).
 */
export function buildFormNav({ form, base, pathname, can, formRevisionsUiEnabled, t }: NavInput): FormNavItem[] {
    const on = (...paths: string[]) => paths.some((path) => pathname.includes(`/${path}`));
    const isFormOpen = validateFormOpen(form?.settings?.formCloseDate);
    const deletion = (icon: LucideIcon): FormNavItem => ({ key: 'deletion-requests', label: t(formConstant.deletionRequests), href: `${base}/deletion-requests`, icon, count: form?.deletionRequests ?? 0, active: on('deletion-requests') });
    const items: FormNavItem[] = [{ key: 'preview', label: t('STAFF.FORM_PAGES.PAGES'), href: `${base}/preview`, icon: LayoutGrid, active: on('preview') }];

    if (form?.isPublished) {
        if (can(WorkspacePermission.RESPONSE_READ)) {
            items.push({
                key: 'responses',
                label: t('FORM_SHELL.RESPONSES_TAB'),
                href: `${base}/responses`,
                icon: Inbox,
                count: form.responses ?? 0,
                active: on('responses', 'deletion-requests'),
                children: can(WorkspacePermission.PRIVACY_MANAGE) ? [deletion(Trash2)] : undefined
            });
        } else if (can(WorkspacePermission.PRIVACY_MANAGE)) {
            // a privacy officer handles deletion requests, never answers
            items.push(deletion(Inbox));
        }
        if (isFormOpen) {
            items.push({ key: 'analytics', label: t('FORM_SHELL.ANALYTICS_TAB'), href: `${base}/analytics`, icon: BarChart3, active: on('analytics') });
            items.push({ key: 'links', label: t('FORM_SHELL.SHARE_TAB'), href: `${base}/links`, icon: Share2, active: on('links') });
        }
        // the published versions of the form: list, compare, restore (the server's FORM_REVISIONS_UI_ENABLED)
        if (formRevisionsUiEnabled && can(WorkspacePermission.FORM_READ)) {
            items.push({ key: 'versions', label: t('FORM_VERSIONS.TAB'), href: `${base}/versions`, icon: History, active: on('versions') });
        }
    }
    if (can(WorkspacePermission.FORM_EDIT)) {
        items.push({
            key: 'settings',
            label: t(localesCommon.settings),
            href: `${base}/settings/access`,
            icon: Settings,
            active: on('settings', 'visibility', 'integrations'),
            opensInPlace: true,
            // only the pages this form has something on
            children: settingsPages(form, can).map((page) => ({ key: `settings-${page}`, label: t(SETTINGS_PAGE_LABELS[page]), href: `${base}/settings/${page}`, icon: SETTINGS_PAGE_ICONS[page], active: on(`settings/${page}`) }))
        });
    }
    return items;
}

/** The item that is the page itself: a sub-page when one is open, else the section (this one carries `aria-current`). */
export function currentItem(items: FormNavItem[]): FormNavItem | undefined {
    for (const item of items) {
        const child = item.children?.find((c) => c.active);
        if (child) return child;
        if (item.active) return item;
    }
    return undefined;
}

export function useFormNav(form: StandardFormDto, base: string): FormNavItem[] {
    const { t } = useTranslation();
    const pathname = usePathname() ?? '';
    const { can, formRevisionsUiEnabled } = useWorkspacePermissions();
    return useMemo(() => buildFormNav({ form, base, pathname, can, formRevisionsUiEnabled: !!formRevisionsUiEnabled, t: (key) => t(key) }), [form, base, pathname, can, formRevisionsUiEnabled, t]);
}

/* --------------------------------------------------------------- the bar */

/** The workspace's mark: its logo, else its first letter. The letter is drawn by CSS so the link's name stays "Forms". */
function WorkspaceMark() {
    const workspace = useAppSelector(selectWorkspace);
    const initial = (workspace?.title?.[0] || workspace?.workspaceName?.[0] || 'W').toUpperCase();
    return workspace?.profileImage ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={workspace.profileImage} alt="" className="h-7 w-7 shrink-0 rounded-md object-cover" />
    ) : (
        <span data-initial={initial} aria-hidden="true" className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-brand-100 text-xs font-bold text-brand-600 before:content-[attr(data-initial)]" />
    );
}

/** Back to the forms list: a real link, so it also opens in a new tab. */
export function BackToForms() {
    const { t } = useTranslation();
    const workspace = useAppSelector(selectWorkspace);
    return (
        <Link
            href={`/${workspace?.workspaceName}/dashboard/forms`}
            aria-label={t('FORM_NAV.BACK')}
            title={t('FORM_NAV.BACK')}
            className="-ml-1 flex h-11 shrink-0 items-center gap-1.5 rounded px-2 text-sm font-medium text-black-700 hover:bg-black-200 hover:text-black-900"
        >
            <ArrowLeft className="h-[18px] w-[18px]" aria-hidden="true" />
            <WorkspaceMark />
            <span className="hidden md:inline">{t('FORM_SHELL.FORMS')}</span>
        </Link>
    );
}

export function StatusChip({ form, className }: { form: StandardFormDto; className?: string }) {
    const { t } = useTranslation();
    return form?.isPublished ? (
        <span className={cn('shrink-0 rounded-full bg-[#E7F4EE] px-2 py-0.5 text-xs font-semibold text-success-700', className)}>{t('FORM_SHELL.PUBLISHED')}</span>
    ) : (
        <span className={cn('shrink-0 rounded-full bg-black-200 px-2 py-0.5 text-xs font-semibold text-black-700', className)}>{t('FORM_SHELL.DRAFT')}</span>
    );
}

/** The first stop of the page: jumps over the bar to the form's content. */
export function SkipLink() {
    const { t } = useTranslation();
    return (
        <a href="#form-main" className="sr-only z-[5000] rounded bg-brand-500 px-4 py-2 text-white focus:not-sr-only focus:fixed focus:top-3 focus:left-3">
            {t('FORM_NAV.SKIP')}
        </a>
    );
}

/** Preview, Edit, Share (Publish for a draft) and the form's menu. Below `md` only Share and the menu stay; Preview moves into the menu. */
export function FormBarActions({ form }: { form: StandardFormDto }) {
    const { t } = useTranslation();
    const router = useRouter();
    const { openModal } = useModal();
    const { openModal: openFullScreenModal } = useFullScreenModal();
    const workspace = useAppSelector(selectWorkspace);
    const { can } = useWorkspacePermissions();
    const isPhone = useIsPhone();
    const isFormOpen = validateFormOpen(form?.settings?.formCloseDate);
    const canEdit = can(WorkspacePermission.FORM_EDIT);
    const v2 = form?.builderVersion === 'v2';
    const preview = () => openFullScreenModal('PREVIEW_MODAL');

    return (
        <div className="flex items-center gap-2">
            {v2 && (
                <Button variant="v2Button" icon={<Play className="h-[18px] w-[18px]" aria-hidden="true" />} aria-label={t('FORM_SHELL.PREVIEW')} onClick={preview} className="hidden px-3 md:flex lg:px-4">
                    <span className="hidden lg:inline">{t('FORM_SHELL.PREVIEW')}</span>
                </Button>
            )}
            {canEdit && form?.settings?.provider === 'self' && v2 && (
                <Button variant="v2Button" icon={<Edit2 className="h-[18px] w-[18px]" aria-hidden="true" />} aria-label={t(buttonConstant.edit)} onClick={() => router.push(getEditFormURL(workspace, form))} className="hidden px-3 md:flex lg:px-4">
                    <span className="hidden lg:inline">{t(buttonConstant.edit)}</span>
                </Button>
            )}
            {form?.isPublished
                ? isFormOpen && (
                      <PrivateFormButtonWrapper isPrivate={form?.settings?.hidden}>
                          <Button
                              variant="primary"
                              icon={<Share2 className="h-[18px] w-[18px]" aria-hidden="true" />}
                              aria-label={t('FORM_SHELL.SHARE')}
                              disabled={form?.settings?.hidden}
                              className="h-11 w-11 px-0 sm:h-10 sm:w-auto sm:px-4"
                              onClick={() => openModal('SHARE_VIEW', { url: getFormShareURL(form, workspace), title: t(formConstant.shareThisForm), formTitle: form?.title })}
                          >
                              <span className="hidden sm:inline">{t('FORM_SHELL.SHARE')}</span>
                          </Button>
                      </PrivateFormButtonWrapper>
                  )
                : canEdit && <PublishButton refresh />}
            <FormOptionsDropdownMenu workspace={workspace} form={form} hasCustomDomain={false} redirectToDashboard inHeader onPreview={isPhone && v2 ? preview : undefined} className="flex h-11 w-11 items-center justify-center md:h-10 md:w-10" />
        </div>
    );
}
