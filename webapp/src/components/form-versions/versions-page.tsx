'use client';

import React, { useState } from 'react';

import Link from 'next/link';

import { useTranslation } from 'react-i18next';

import { useWorkspacePermissions } from '@app/lib/hooks/use-workspace-permissions';
import { WorkspacePermission } from '@app/models/enums/workspace-permission';
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '@app/shadcn/components/ui/alert-dialog';
import { buttonClassName } from '@app/shadcn/components/ui/button';
import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { FormVersionSummary, VersionAuthor, useGetFormVersionsQuery, useRestoreFormVersionMutation } from '@app/store/workspaces/form-versions-api';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { utcToLocalDateTimeIn } from '@app/utils/date-utils';
import { formVersionCompareUrl, formVersionUrl } from '@app/utils/response-urls';
import { getEditFormURL } from '@app/utils/url-utils';

const actionLink = buttonClassName({ variant: 'v2Button', size: 'sm', className: '' });

/** The versions of a form: who published each and when, with View, Compare and Restore. */
export default function FormVersionsPage() {
    const { t, i18n } = useTranslation();
    const workspace = useAppSelector(selectWorkspace);
    const form = useAppSelector(selectForm);
    const { can, ready, formRevisionsUiEnabled } = useWorkspacePermissions();
    const workspaceId = workspace?.id ?? '';
    const formId = form?.formId ?? '';
    const allowed = formRevisionsUiEnabled && can(WorkspacePermission.FORM_READ);
    const { data, isLoading, isError, error, refetch } = useGetFormVersionsQuery({ workspaceId, formId }, { skip: !allowed || !workspaceId || !formId });
    const [restore, { isLoading: restoring }] = useRestoreFormVersionMutation();
    const [target, setTarget] = useState<FormVersionSummary | null>(null);
    const [failure, setFailure] = useState<string | null>(null);
    const [restored, setRestored] = useState<number | null>(null);
    const canRestore = can(WorkspacePermission.FORM_EDIT) && (form?.settings?.provider ?? 'self') === 'self';

    if (!ready) return <div className="px-4 md:px-10 lg:px-28" role="status" aria-live="polite" />;
    if (!allowed) {
        return (
            <div className="px-4 md:px-10 lg:px-28">
                <p role="status" className="max-w-2xl text-sm text-black-700">
                    {t('FORM_VERSIONS.DISABLED')}
                </p>
            </div>
        );
    }

    const versions = data?.versions ?? [];
    const draft = data?.draft;
    const newest = versions[0]?.version;
    const when = (value?: string | null) => (value ? utcToLocalDateTimeIn(value, i18n.language) : '');

    const confirmRestore = async () => {
        if (!target || !draft?.updatedAt) return;
        setFailure(null);
        const result: any = await restore({ workspaceId, formId, version: target.version, expectedUpdatedAt: draft.updatedAt, replaceDraft: !!draft.hasUnpublishedChanges });
        if (result?.error) {
            const code = result.error?.data?.code;
            setFailure(t(`FORM_VERSIONS.ERROR.${typeof code === 'string' && code !== 'generic' ? code : 'generic'}`, { defaultValue: t('FORM_VERSIONS.ERROR.generic') }));
        } else {
            setRestored(target.version);
            setTarget(null);
        }
    };

    return (
        <div className="px-4 md:px-10 lg:px-28" data-testid="form-versions">
            <section aria-labelledby="form-versions-title" className="flex max-w-3xl flex-col gap-4">
                <div className="flex flex-col gap-1">
                    <h2 id="form-versions-title" className="text-lg font-semibold">
                        {t('FORM_VERSIONS.TITLE')}
                    </h2>
                    <p className="text-sm text-black-700">{t('FORM_VERSIONS.INTRO')}</p>
                </div>

                {/* what a screen reader hears after a restore or a failed one */}
                <div role="status" aria-live="polite" className={restored !== null || failure ? 'rounded border border-black-300 bg-white px-3 py-2 text-sm' : 'sr-only'}>
                    {restored !== null && (
                        <p>
                            {t('FORM_VERSIONS.RESTORED', { n: restored })}{' '}
                            <Link href={getEditFormURL(workspace, form)} className="underline underline-offset-2">
                                {t('FORM_VERSIONS.OPEN_BUILDER')}
                            </Link>
                        </p>
                    )}
                    {failure && !target && <p>{failure}</p>}
                </div>

                {isLoading && (
                    <p role="status" className="text-sm text-black-700">
                        {t('FORM_VERSIONS.LOADING')}
                    </p>
                )}
                {isError && (
                    <div role="alert" className="flex flex-wrap items-center gap-3 text-sm">
                        <span>{(error as any)?.data?.code === 'form_revisions_disabled' ? t('FORM_VERSIONS.DISABLED') : t('FORM_VERSIONS.LOAD_ERROR')}</span>
                        <button type="button" className={actionLink} onClick={() => refetch()}>
                            {t('FORM_VERSIONS.RETRY')}
                        </button>
                    </div>
                )}

                {!isLoading && !isError && (
                    <>
                        {draft && (
                            <div className="flex flex-col gap-2 rounded border border-black-300 bg-white p-4" data-testid="draft-row">
                                <div className="flex flex-wrap items-center gap-2">
                                    <h3 className="font-medium">{t('FORM_VERSIONS.DRAFT')}</h3>
                                    <span className="text-sm text-black-700">{draft.hasUnpublishedChanges ? t('FORM_VERSIONS.DRAFT_CHANGED') : t('FORM_VERSIONS.DRAFT_SAME')}</span>
                                </div>
                                {draft.hasUnpublishedChanges && newest !== undefined && (
                                    <div className="flex flex-wrap gap-2">
                                        <Link href={formVersionCompareUrl(workspace.workspaceName, formId, newest, 'draft')} className={actionLink} aria-label={t('FORM_VERSIONS.COMPARE_DRAFT_NAMED')}>
                                            {t('FORM_VERSIONS.COMPARE_DRAFT')}
                                        </Link>
                                    </div>
                                )}
                            </div>
                        )}

                        {versions.length === 0 ? (
                            <p className="text-sm text-black-700">{t('FORM_VERSIONS.NO_VERSIONS')}</p>
                        ) : (
                            <ul aria-label={t('FORM_VERSIONS.TABLE_LABEL')} className="flex flex-col gap-3">
                                {versions.map((item, index) => {
                                    const previous = versions[index + 1];
                                    return (
                                        <li key={item.version} className="flex flex-col gap-2 rounded border border-black-300 bg-white p-4" data-testid={`version-${item.version}`}>
                                            <div className="flex flex-wrap items-center gap-2">
                                                <h3 className="font-medium">{t('FORM_VERSIONS.VERSION_N', { n: item.version })}</h3>
                                                {item.current && <span className="bg-success-100 rounded-full px-2 py-0.5 text-xs font-semibold text-success-700">{t('FORM_VERSIONS.LIVE')}</span>}
                                            </div>
                                            <p className="text-sm text-black-700">
                                                {when(item.publishedAt)}
                                                {when(item.publishedAt) ? ' · ' : ''}
                                                {authorText(t, item.publishedBy)}
                                            </p>
                                            <div className="flex flex-wrap gap-2">
                                                <Link href={formVersionUrl(workspace.workspaceName, formId, item.version)} className={actionLink} aria-label={t('FORM_VERSIONS.VIEW_NAMED', { n: item.version })}>
                                                    {t('FORM_VERSIONS.VIEW')}
                                                </Link>
                                                {previous && (
                                                    <Link href={formVersionCompareUrl(workspace.workspaceName, formId, previous.version, item.version)} className={actionLink} aria-label={t('FORM_VERSIONS.COMPARE_PREVIOUS_NAMED', { n: item.version })}>
                                                        {t('FORM_VERSIONS.COMPARE_PREVIOUS')}
                                                    </Link>
                                                )}
                                                {canRestore && (
                                                    <button
                                                        type="button"
                                                        className={actionLink}
                                                        aria-label={t('FORM_VERSIONS.RESTORE_NAMED', { n: item.version })}
                                                        onClick={() => {
                                                            setFailure(null);
                                                            setRestored(null);
                                                            setTarget(item);
                                                        }}
                                                    >
                                                        {t('FORM_VERSIONS.RESTORE')}
                                                    </button>
                                                )}
                                            </div>
                                        </li>
                                    );
                                })}
                            </ul>
                        )}
                    </>
                )}
            </section>

            <AlertDialog open={target !== null} onOpenChange={(open: boolean) => !open && !restoring && setTarget(null)}>
                <AlertDialogContent>
                    <AlertDialogHeader>
                        <AlertDialogTitle>{t('FORM_VERSIONS.RESTORE_TITLE', { n: target?.version })}</AlertDialogTitle>
                        <AlertDialogDescription asChild>
                            <div className="flex flex-col gap-2">
                                <p>{t('FORM_VERSIONS.RESTORE_BODY', { n: target?.version })}</p>
                                {draft?.hasUnpublishedChanges && <p className="font-medium">{t('FORM_VERSIONS.RESTORE_REPLACES')}</p>}
                                <p>{t('FORM_VERSIONS.RESTORE_KEEPS')}</p>
                                {failure && (
                                    <p role="alert" className="text-danger-700">
                                        {failure}
                                    </p>
                                )}
                            </div>
                        </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                        <AlertDialogCancel disabled={restoring}>{t('FORM_VERSIONS.CANCEL')}</AlertDialogCancel>
                        <AlertDialogAction
                            disabled={restoring}
                            onClick={(event: React.MouseEvent) => {
                                event.preventDefault();
                                confirmRestore();
                            }}
                        >
                            {t('FORM_VERSIONS.RESTORE_CONFIRM')}
                        </AlertDialogAction>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>
        </div>
    );
}

function authorText(t: (key: string, options?: any) => string, author?: VersionAuthor | null): string {
    if (!author) return t('FORM_VERSIONS.BY_UNKNOWN');
    if (author.former) return t('FORM_VERSIONS.BY_FORMER');
    const role = author.role ? t(`WORKSPACE_ROLES.${author.role}.NAME`, { defaultValue: '' }) : '';
    if (author.name && role) return t('FORM_VERSIONS.BY_MEMBER', { name: author.name, role });
    if (author.name) return t('FORM_VERSIONS.BY_NAME', { name: author.name });
    if (role) return t('FORM_VERSIONS.BY_ROLE', { role });
    return t('FORM_VERSIONS.BY_UNKNOWN');
}
