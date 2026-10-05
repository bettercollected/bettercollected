'use client';

import { FormEvent, useState } from 'react';

import { TFunction } from 'i18next';
import { AlertTriangle, RefreshCw, ShieldCheck, Users } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import { CopyField, Section, errorMessage, formatTime, inputClass } from '@app/components/workspace-sso/workspace-sso-section';
import { scim } from '@app/constants/locales/scim';
import { ScimCredentialsDto, ScimGroupDto, ScimOverviewDto } from '@app/models/dtos/workspace-scim-dto';
import { roleLocale, toWorkspaceRole } from '@app/models/enums/workspace-role';
import { Button } from '@app/shadcn/components/ui/button';
import { useToast } from '@app/shadcn/components/ui/use-toast';
import { cn } from '@app/shadcn/util/lib';
import { useAppSelector } from '@app/store/hooks';
import { useCleanupScimDirectoryMutation, useCreateScimDirectoryMutation, useDeleteScimDirectoryMutation, useGetWorkspaceScimQuery, useResyncScimDirectoryMutation, useRotateScimTokenMutation, useSetScimGroupRoleMutation } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';

// What a failed resync (``lastResyncError``) means.
const RESYNC_ERRORS: Record<string, string> = scim.RESYNC_ERRORS;

function roleLabel(t: TFunction, role?: string | null): string {
    if (!role) return t(scim.NO_ROLE);
    const known = toWorkspaceRole(role);
    return known ? t(roleLocale(known).name) : role;
}

const COUNT_KEYS: Array<keyof typeof scim.COUNTS> = ['provisioned', 'deprovisioned', 'failed', 'ignored'];

/** The base URL and token, shown once after creating or rotating. */
function Credentials({ credentials, onDone }: { credentials: ScimCredentialsDto; onDone: () => void }) {
    const { t } = useTranslation();
    return (
        <div role="status" className="flex flex-col gap-3 rounded-lg border border-[#F2D9A6] bg-[#FDF8EC] p-4" data-testid="scim-credentials">
            <p className="flex items-start gap-2 text-xs leading-relaxed text-black-800">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-[#9A5B00]" />
                <span>{t(scim.CREDENTIALS_NOTICE)}</span>
            </p>
            <CopyField label={t(scim.BASE_URL)} value={credentials.scimEndpoint} />
            <CopyField label={t(scim.BEARER_TOKEN)} value={credentials.bearerToken} />
            <div>
                <Button size="sm" variant="primary" onClick={onDone}>
                    {t(scim.COPIED)}
                </Button>
            </div>
        </div>
    );
}

function CreateDirectoryForm({ overview, workspaceId, onCreated }: { overview: ScimOverviewDto; workspaceId: string; onCreated: (c: ScimCredentialsDto) => void }) {
    const { t } = useTranslation();
    const [create, { isLoading }] = useCreateScimDirectoryMutation();
    const [type, setType] = useState(overview.types[0]?.type ?? 'generic-scim-v2');
    const [error, setError] = useState<string | null>(null);

    const submit = async (event: FormEvent) => {
        event.preventDefault();
        setError(null);
        const response: any = await create({ workspace_id: workspaceId, body: { type } });
        if (response.error) {
            setError(errorMessage(response.error, t(scim.CREATE_FAILED)));
            return;
        }
        onCreated(response.data);
    };

    return (
        <form onSubmit={submit} className="flex flex-col gap-3 rounded-lg border border-black-200 bg-white p-4" noValidate>
            <label className="flex flex-col gap-1 text-xs font-medium text-black-800">
                {t(scim.IDENTITY_PROVIDER)}
                <select className={cn(inputClass, 'sm:max-w-[280px]')} value={type} onChange={(e) => setType(e.target.value)}>
                    {overview.types.map((option) => (
                        <option key={option.type} value={option.type}>
                            {option.label}
                        </option>
                    ))}
                </select>
            </label>
            {!overview.hasVerifiedDomain && <p className="text-xs text-black-500">{t(scim.VERIFY_DOMAIN_FIRST)}</p>}
            {error && (
                <p role="alert" className="text-xs text-[#C43D3D]">
                    {error}
                </p>
            )}
            <div>
                <Button type="submit" size="sm" variant="primary" isLoading={isLoading} disabled={!overview.hasVerifiedDomain}>
                    {t(scim.CREATE)}
                </Button>
            </div>
        </form>
    );
}

function GroupRow({ group, overview, workspaceId }: { group: ScimGroupDto; overview: ScimOverviewDto; workspaceId: string }) {
    const { t } = useTranslation();
    const { toast } = useToast();
    const [setRole, { isLoading }] = useSetScimGroupRoleMutation();
    const change = async (role: string) => {
        const response: any = await setRole({ workspace_id: workspaceId, group_id: group.id, role: role || null });
        if (response.error) toast({ description: errorMessage(response.error, t(scim.MAPPING_FAILED)), variant: 'destructive' });
        else toast({ description: t(scim.MAPPING_SAVED, { group: group.name, role: roleLabel(t, role || null) }) });
    };
    return (
        <tr className="border-t border-black-100">
            <td className="break-all py-2 pr-3 text-sm text-black-900">
                {group.name}
                {group.needsReview && (
                    <span className="ml-2 rounded bg-[#FDF3E3] px-1.5 py-0.5 text-[11px] font-medium text-[#9A5B00]" title={t(scim.CHECK_ROLE_HINT)}>
                        {t(scim.CHECK_ROLE)}
                    </span>
                )}
            </td>
            <td className="py-2 pr-3 text-xs text-black-600">{group.members}</td>
            <td className="py-2">
                <select aria-label={t(scim.ROLE_FOR, { group: group.name })} className={cn(inputClass, 'h-8 sm:max-w-[200px]')} value={group.role ?? ''} disabled={!overview.canManage || isLoading} onChange={(e) => change(e.target.value)}>
                    <option value="">{t(scim.NO_ROLE)}</option>
                    {overview.mappableRoles.map((role) => (
                        <option key={role} value={role}>
                            {roleLabel(t, role)}
                        </option>
                    ))}
                </select>
            </td>
        </tr>
    );
}

/**
 * Directory sync (SCIM, docs/sso.md): the identity provider creates,
 * deactivates and assigns roles to members through a SCIM directory held by
 * the single sign-on service. Owner manages; Admins (security.manage) view.
 */
export default function WorkspaceScimSection() {
    const { t } = useTranslation();
    const workspace = useAppSelector(selectWorkspace);
    const workspaceId: string = workspace?.id;
    const { toast } = useToast();
    const { data: overview, isLoading, isError, refetch } = useGetWorkspaceScimQuery(workspaceId, { skip: !workspaceId });
    const [rotate, { isLoading: isRotating }] = useRotateScimTokenMutation();
    const [remove, { isLoading: isDeleting }] = useDeleteScimDirectoryMutation();
    const [resync, { isLoading: isResyncing }] = useResyncScimDirectoryMutation();
    const [cleanup, { isLoading: isCleaning }] = useCleanupScimDirectoryMutation();
    const [credentials, setCredentials] = useState<ScimCredentialsDto | null>(null);

    const title = t(scim.TITLE);
    const description = t(scim.DESCRIPTION);

    if (isLoading) return null;
    if (isError || !overview) {
        return (
            <Section title={title}>
                <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-[#F3D1D1] bg-[#FBEFEF] px-3 py-3 text-xs text-[#C43D3D]">
                    <span>{t(scim.LOAD_FAILED)}</span>
                    <Button size="sm" variant="v2Button" onClick={() => refetch()}>
                        {t(scim.TRY_AGAIN)}
                    </Button>
                </div>
            </Section>
        );
    }
    if (!overview.available) {
        return (
            <Section title={title} description={description}>
                <p className="rounded-md border border-dashed border-black-200 px-3 py-4 text-xs text-black-600">{t(scim.NOT_ENABLED)}</p>
            </Section>
        );
    }

    const directory = overview.directory;

    const doRotate = async () => {
        if (!window.confirm(t(scim.CONFIRM_ROTATE))) return;
        const response: any = await rotate({ workspace_id: workspaceId });
        if (response.error) {
            toast({ description: errorMessage(response.error, t(scim.ROTATE_FAILED)), variant: 'destructive' });
            return;
        }
        setCredentials(response.data);
        if (response.data?.previousDirectoryDeleted === false) {
            toast({ description: t(scim.ROTATE_STALE), variant: 'destructive' });
        }
    };

    const doDelete = async () => {
        if (!window.confirm(t(scim.CONFIRM_DELETE))) return;
        const response: any = await remove({ workspace_id: workspaceId });
        if (response.error) toast({ description: errorMessage(response.error, t(scim.DELETE_FAILED)), variant: 'destructive' });
        else {
            const left = response.data?.leftDisabled ?? 0;
            toast({ description: left ? t(scim.DELETED_LEFT, { count: left }) : t(scim.DELETED) });
        }
    };

    const doResync = async (force = false) => {
        const response: any = await resync({ workspace_id: workspaceId, force });
        const refusal = response.error?.data;
        if (!force && refusal?.code === 'mass_deprovision_refused') {
            const { wouldDeprovision, provisioned } = refusal.summary ?? {};
            if (window.confirm(t(scim.CONFIRM_FORCE, { count: wouldDeprovision, total: provisioned }))) {
                await doResync(true);
            }
            return;
        }
        if (response.error) toast({ description: errorMessage(response.error, t(scim.RESYNC_FAILED)), variant: 'destructive' });
        else toast({ description: t(scim.RESYNCED, { users: response.data.summary.users ?? 0, groups: response.data.summary.groups ?? 0 }) });
    };

    const doCleanup = async () => {
        const response: any = await cleanup({ workspace_id: workspaceId });
        if (response.error) toast({ description: errorMessage(response.error, t(scim.CLEANUP_FAILED)), variant: 'destructive' });
        else toast({ description: t(scim.CLEANED_UP) });
    };

    return (
        <Section title={title} description={description}>
            {!overview.canManage && (
                <div role="note" className="flex items-start gap-2 rounded-md border border-[#D6E2F5] bg-[#F3F7FD] p-3 text-xs leading-relaxed text-black-700">
                    <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-brand-500" />
                    <span>{t(scim.OWNER_ONLY)}</span>
                </div>
            )}
            {credentials && <Credentials credentials={credentials} onDone={() => setCredentials(null)} />}

            {!directory ? (
                overview.canManage ? (
                    <CreateDirectoryForm overview={overview} workspaceId={workspaceId} onCreated={setCredentials} />
                ) : (
                    <p className="rounded-md border border-dashed border-black-200 px-3 py-3 text-xs text-black-600">{t(scim.NO_DIRECTORY)}</p>
                )
            ) : (
                <>
                    <div className="flex flex-col gap-3 rounded-lg border border-black-200 bg-white p-4" data-testid="scim-directory">
                        <div className="flex flex-wrap items-start justify-between gap-3">
                            <div className="flex min-w-0 flex-col gap-1">
                                <div className="flex flex-wrap items-center gap-2">
                                    <Users className="h-4 w-4 shrink-0 text-[#0E8A5F]" />
                                    <span className="text-sm font-semibold text-black-900">{directory.typeLabel}</span>
                                    <span className="rounded bg-[#E7F6EE] px-1.5 py-0.5 text-[11px] font-medium text-[#0E8A5F]">{t(scim.SYNCING)}</span>
                                </div>
                                <span className="text-xs text-black-500">{directory.lastEventAt ? t(scim.LAST_CHANGE, { time: formatTime(directory.lastEventAt), type: directory.lastEventType }) : t(scim.NO_CHANGE)}</span>
                                {directory.lastResyncAt && (
                                    <span className="text-xs text-black-500">
                                        {directory.lastResyncError
                                            ? t(scim.LAST_RESYNC_FAILED, { time: formatTime(directory.lastResyncAt), reason: t(RESYNC_ERRORS[directory.lastResyncError] ?? RESYNC_ERRORS.resync_failed) })
                                            : t(scim.LAST_RESYNC, { time: formatTime(directory.lastResyncAt) })}
                                    </span>
                                )}
                            </div>
                            {overview.canManage && (
                                <div className="flex shrink-0 flex-wrap items-center gap-2">
                                    <Button size="sm" variant="v2Button" isLoading={isResyncing} onClick={() => doResync()} icon={<RefreshCw className="h-3.5 w-3.5" />}>
                                        {t(scim.RESYNC)}
                                    </Button>
                                    <Button size="sm" variant="v2Button" isLoading={isRotating} onClick={doRotate}>
                                        {t(scim.ROTATE)}
                                    </Button>
                                    <Button size="sm" variant="dangerGhost" isLoading={isDeleting} onClick={doDelete}>
                                        {t(scim.DELETE)}
                                    </Button>
                                </div>
                            )}
                        </div>
                        {directory.previousDirectoryPendingDelete && (
                            <div role="alert" className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-[#F2D9A6] bg-[#FDF8EC] px-3 py-2 text-xs text-black-800" data-testid="scim-stale-directory">
                                <span>{t(scim.STALE_DIRECTORY)}</span>
                                {overview.canManage && (
                                    <Button size="sm" variant="v2Button" isLoading={isCleaning} onClick={doCleanup}>
                                        {t(scim.RETRY)}
                                    </Button>
                                )}
                            </div>
                        )}
                        {directory.rotationGraceUntil && <p className="text-xs text-black-600">{t(scim.ROTATION_GRACE, { time: formatTime(directory.rotationGraceUntil) })}</p>}
                        <CopyField label={t(scim.BASE_URL)} value={directory.scimEndpoint} hint={t(scim.TOKEN_HINT)} />
                        <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                            {COUNT_KEYS.map((key) => (
                                <div key={key} className="bg-black-50 rounded-md px-3 py-2">
                                    <dt className="text-[11px] uppercase tracking-wide text-black-500">{t(scim.COUNTS[key])}</dt>
                                    <dd className={cn('text-lg font-semibold', key === 'failed' && (overview.counts[key] ?? 0) > 0 ? 'text-[#C43D3D]' : 'text-black-900')}>{overview.counts[key] ?? 0}</dd>
                                </div>
                            ))}
                        </dl>
                    </div>

                    {overview.issues.length > 0 && (
                        <div className="flex flex-col gap-2">
                            <h3 className="text-xs font-semibold text-black-800">{t(scim.NEEDS_ATTENTION)}</h3>
                            <ul className="flex flex-col gap-1.5" data-testid="scim-issues">
                                {overview.issues.map((issue) => (
                                    <li key={`${issue.email}-${issue.reason}`} className={cn('flex flex-col gap-0.5 rounded-md border px-3 py-2 text-xs', issue.state === 'failed' ? 'border-[#F3D1D1] bg-[#FBEFEF]' : 'border-black-200 bg-white')}>
                                        <span className="break-all font-medium text-black-900">{issue.email || t(scim.UNKNOWN_USER)}</span>
                                        <span className="text-black-700">{issue.message}</span>
                                    </li>
                                ))}
                            </ul>
                        </div>
                    )}

                    <div className="flex flex-col gap-2">
                        <h3 className="text-xs font-semibold text-black-800">{t(scim.GROUPS_TITLE)}</h3>
                        <p className="max-w-[62ch] text-xs leading-relaxed text-black-600">{t(scim.GROUPS_DESCRIPTION, { role: roleLabel(t, overview.defaultRole) })}</p>
                        {overview.groups.length ? (
                            <table className="w-full text-left">
                                <thead>
                                    <tr className="text-[11px] uppercase tracking-wide text-black-500">
                                        <th className="pb-1 font-medium">{t(scim.GROUP)}</th>
                                        <th className="pb-1 font-medium">{t(scim.MEMBERS)}</th>
                                        <th className="pb-1 font-medium">{t(scim.ROLE)}</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {overview.groups.map((group) => (
                                        <GroupRow key={group.id} group={group} overview={overview} workspaceId={workspaceId} />
                                    ))}
                                </tbody>
                            </table>
                        ) : (
                            <p className="rounded-md border border-dashed border-black-200 px-3 py-3 text-xs text-black-600">{t(scim.NO_GROUPS)}</p>
                        )}
                    </div>
                </>
            )}
        </Section>
    );
}
