'use client';

import Link from 'next/link';

import { useTranslation } from 'react-i18next';

import { useWorkspacePermissions } from '@app/lib/hooks/use-workspace-permissions';
import { WorkspacePermission } from '@app/models/enums/workspace-permission';
import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { useCompareFormVersionsQuery } from '@app/store/workspaces/form-versions-api';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { formVersionsUrl } from '@app/utils/response-urls';
import { describeChange, groupChanges } from '@app/utils/version-changes';

const SIDE = /^(\d{1,9}|draft)$/;

/**
 * What changed going from one version (or the draft) to another, worded in
 * the viewer's language from the server's coded entries. Form content only.
 */
export default function VersionCompare({ from, to }: { from: string; to: string }) {
    const { t } = useTranslation();
    const workspace = useAppSelector(selectWorkspace);
    const form = useAppSelector(selectForm);
    const { can, ready, formRevisionsUiEnabled } = useWorkspacePermissions();
    const workspaceId = workspace?.id ?? '';
    const formId = form?.formId ?? '';
    const valid = SIDE.test(from) && SIDE.test(to);
    const allowed = formRevisionsUiEnabled && can(WorkspacePermission.FORM_READ);
    const { data, isLoading, isError, error } = useCompareFormVersionsQuery({ workspaceId, formId, from, to }, { skip: !allowed || !valid || !workspaceId || !formId });
    const back = formVersionsUrl(workspace?.workspaceName ?? '', formId);
    const side = (value: string) => (value === 'draft' ? t('FORM_VERSIONS.COMPARE.SIDE_DRAFT') : t('FORM_VERSIONS.COMPARE.SIDE_VERSION', { n: value }));

    if (!ready) return <div className="px-4 md:px-10 lg:px-28" role="status" aria-live="polite" />;
    if (!allowed) {
        return (
            <div className="px-4 md:px-10 lg:px-28">
                <p role="status" className="text-black-700 text-sm">
                    {t('FORM_VERSIONS.DISABLED')}
                </p>
            </div>
        );
    }
    const failureCode = (error as any)?.data?.code;

    return (
        <div className="px-4 md:px-10 lg:px-28" data-testid="version-compare">
            <section aria-labelledby="version-compare-title" className="flex max-w-3xl flex-col gap-4">
                <Link href={back} className="text-black-700 hover:text-black-900 w-fit text-sm underline underline-offset-2">
                    {t('FORM_VERSIONS.VIEW_PAGE.BACK')}
                </Link>
                <div className="flex flex-col gap-1">
                    <h2 id="version-compare-title" className="text-lg font-semibold">
                        {t('FORM_VERSIONS.COMPARE.TITLE')}
                    </h2>
                    {valid && <p className="text-black-700 text-sm">{t('FORM_VERSIONS.COMPARE.FROM_TO', { from: side(from), to: side(to) })}</p>}
                </div>
                {!valid && (
                    <p role="alert" className="text-sm">
                        {t('FORM_VERSIONS.VIEW_PAGE.NOT_FOUND')}
                    </p>
                )}
                {valid && isLoading && (
                    <p role="status" className="text-black-700 text-sm">
                        {t('FORM_VERSIONS.LOADING')}
                    </p>
                )}
                {isError && (
                    <p role="alert" className="text-sm">
                        {failureCode === 'not_comparable' ? t('FORM_VERSIONS.COMPARE.NOT_COMPARABLE') : (error as any)?.status === 404 ? t('FORM_VERSIONS.VIEW_PAGE.NOT_FOUND') : t('FORM_VERSIONS.LOAD_ERROR')}
                    </p>
                )}
                {data && (
                    <>
                        {!data.changed && data.entries.length === 0 ? (
                            <p className="text-sm">{t('FORM_VERSIONS.COMPARE.NO_CHANGES')}</p>
                        ) : (
                            <div className="flex flex-col gap-5">
                                {groupChanges(data.entries).map((group) => (
                                    <section key={group.scope} aria-labelledby={`changes-${group.scope}`} className="flex flex-col gap-2">
                                        <h3 id={`changes-${group.scope}`} className="text-black-700 text-xs font-semibold tracking-wide uppercase">
                                            {t(`FORM_VERSIONS.COMPARE.SCOPE_${group.scope}`)}
                                        </h3>
                                        <ul className="border-black-300 flex flex-col divide-y divide-black-300 rounded border bg-white">
                                            {group.changes.map((change, index) => (
                                                <li key={`${change.kind}-${change.ref ?? ''}-${index}`} className="px-4 py-2.5 text-sm break-words">
                                                    {describeChange(t, change)}
                                                </li>
                                            ))}
                                        </ul>
                                    </section>
                                ))}
                            </div>
                        )}
                        {data.truncated && <p className="text-black-700 text-sm">{t('FORM_VERSIONS.COMPARE.TRUNCATED', { count: data.entries.length })}</p>}
                        <p className="text-black-700 text-xs">{t('FORM_VERSIONS.COMPARE.NOTE')}</p>
                    </>
                )}
            </section>
        </div>
    );
}
