'use client';

import { FormEvent, useState } from 'react';

import { AlertTriangle, RefreshCw, ShieldCheck, Users } from 'lucide-react';

import { CopyField, ROLE_LABELS, Section, errorMessage, formatTime, inputClass } from '@app/components/workspace-sso/workspace-sso-section';
import { ScimCredentialsDto, ScimGroupDto, ScimOverviewDto } from '@app/models/dtos/workspace-scim-dto';
import { Button } from '@app/shadcn/components/ui/button';
import { useToast } from '@app/shadcn/components/ui/use-toast';
import { cn } from '@app/shadcn/util/lib';
import { useAppSelector } from '@app/store/hooks';
import { useCleanupScimDirectoryMutation, useCreateScimDirectoryMutation, useDeleteScimDirectoryMutation, useGetWorkspaceScimQuery, useResyncScimDirectoryMutation, useRotateScimTokenMutation, useSetScimGroupRoleMutation } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';

// What a failed resync (``lastResyncError``) means.
const RESYNC_ERRORS: Record<string, string> = {
    scim_unavailable: 'the directory service was not reachable.',
    auth_unavailable: 'the account service was not reachable; some people were skipped.',
    mass_deprovision_refused: 'it would have deactivated too many members at once, so nothing was changed. Check your identity provider, then resync (you can force it).',
    resync_failed: 'something went wrong; it is retried tonight.'
};

const roleLabel = (role?: string | null) => (role ? (ROLE_LABELS[role] ?? role) : 'No role');

const COUNT_LABELS: [string, string][] = [
    ['provisioned', 'Active'],
    ['deprovisioned', 'Deactivated'],
    ['failed', 'Failed'],
    ['ignored', 'Left alone']
];

/** The base URL and token, shown once after creating or rotating. */
function Credentials({ credentials, onDone }: { credentials: ScimCredentialsDto; onDone: () => void }) {
    return (
        <div role="status" className="flex flex-col gap-3 rounded-lg border border-[#F2D9A6] bg-[#FDF8EC] p-4" data-testid="scim-credentials">
            <p className="flex items-start gap-2 text-xs leading-relaxed text-black-800">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-[#9A5B00]" />
                <span>
                    Enter these in your identity provider&apos;s SCIM provisioning settings now. <strong>The token is shown only once</strong>: if you lose it, rotate it.
                </span>
            </p>
            <CopyField label="SCIM base URL" value={credentials.scimEndpoint} />
            <CopyField label="Bearer token" value={credentials.bearerToken} />
            <div>
                <Button size="sm" variant="primary" onClick={onDone}>
                    I&apos;ve copied them
                </Button>
            </div>
        </div>
    );
}

function CreateDirectoryForm({ overview, workspaceId, onCreated }: { overview: ScimOverviewDto; workspaceId: string; onCreated: (c: ScimCredentialsDto) => void }) {
    const [create, { isLoading }] = useCreateScimDirectoryMutation();
    const [type, setType] = useState(overview.types[0]?.type ?? 'generic-scim-v2');
    const [error, setError] = useState<string | null>(null);

    const submit = async (event: FormEvent) => {
        event.preventDefault();
        setError(null);
        const response: any = await create({ workspace_id: workspaceId, body: { type } });
        if (response.error) {
            setError(errorMessage(response.error, 'Could not create the directory.'));
            return;
        }
        onCreated(response.data);
    };

    return (
        <form onSubmit={submit} className="flex flex-col gap-3 rounded-lg border border-black-200 bg-white p-4" noValidate>
            <label className="flex flex-col gap-1 text-xs font-medium text-black-800">
                Identity provider
                <select className={cn(inputClass, 'sm:max-w-[280px]')} value={type} onChange={(e) => setType(e.target.value)}>
                    {overview.types.map((option) => (
                        <option key={option.type} value={option.type}>
                            {option.label}
                        </option>
                    ))}
                </select>
            </label>
            {!overview.hasVerifiedDomain && <p className="text-xs text-black-500">Verify an email domain first: the directory only provisions addresses on your verified domains.</p>}
            {error && (
                <p role="alert" className="text-xs text-[#C43D3D]">
                    {error}
                </p>
            )}
            <div>
                <Button type="submit" size="sm" variant="primary" isLoading={isLoading} disabled={!overview.hasVerifiedDomain}>
                    Create directory
                </Button>
            </div>
        </form>
    );
}

function GroupRow({ group, overview, workspaceId }: { group: ScimGroupDto; overview: ScimOverviewDto; workspaceId: string }) {
    const { toast } = useToast();
    const [setRole, { isLoading }] = useSetScimGroupRoleMutation();
    const change = async (role: string) => {
        const response: any = await setRole({ workspace_id: workspaceId, group_id: group.id, role: role || null });
        if (response.error) toast({ description: errorMessage(response.error, 'Could not change the mapping.'), variant: 'destructive' });
        else toast({ description: `${group.name}: ${roleLabel(role || null)}.` });
    };
    return (
        <tr className="border-t border-black-100">
            <td className="break-all py-2 pr-3 text-sm text-black-900">
                {group.name}
                {group.needsReview && (
                    <span className="ml-2 rounded bg-[#FDF3E3] px-1.5 py-0.5 text-[11px] font-medium text-[#9A5B00]" title="After the token rotation several earlier groups had this name, so its role was not carried over. Choose it again.">
                        Check the role
                    </span>
                )}
            </td>
            <td className="py-2 pr-3 text-xs text-black-600">{group.members}</td>
            <td className="py-2">
                <select aria-label={`Role for ${group.name}`} className={cn(inputClass, 'h-8 sm:max-w-[200px]')} value={group.role ?? ''} disabled={!overview.canManage || isLoading} onChange={(e) => change(e.target.value)}>
                    <option value="">No role (default)</option>
                    {overview.mappableRoles.map((role) => (
                        <option key={role} value={role}>
                            {roleLabel(role)}
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
    const workspace = useAppSelector(selectWorkspace);
    const workspaceId: string = workspace?.id;
    const { toast } = useToast();
    const { data: overview, isLoading, isError, refetch } = useGetWorkspaceScimQuery(workspaceId, { skip: !workspaceId });
    const [rotate, { isLoading: isRotating }] = useRotateScimTokenMutation();
    const [remove, { isLoading: isDeleting }] = useDeleteScimDirectoryMutation();
    const [resync, { isLoading: isResyncing }] = useResyncScimDirectoryMutation();
    const [cleanup, { isLoading: isCleaning }] = useCleanupScimDirectoryMutation();
    const [credentials, setCredentials] = useState<ScimCredentialsDto | null>(null);

    const title = 'Directory sync (SCIM)';
    const description = 'Your identity provider adds people to this workspace, deactivates them when they leave and sets their role from their groups. Only addresses on your verified domains are synced.';

    if (isLoading) return null;
    if (isError || !overview) {
        return (
            <Section title={title}>
                <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-[#F3D1D1] bg-[#FBEFEF] px-3 py-3 text-xs text-[#C43D3D]">
                    <span>Directory sync couldn&apos;t be loaded.</span>
                    <Button size="sm" variant="v2Button" onClick={() => refetch()}>
                        Try again
                    </Button>
                </div>
            </Section>
        );
    }
    if (!overview.available) {
        return (
            <Section title={title} description={description}>
                <p className="rounded-md border border-dashed border-black-200 px-3 py-4 text-xs text-black-600">Directory sync is not enabled on this instance. The operator turns it on (SSO_ENABLED and SCIM_WEBHOOK_URL, see docs/sso.md).</p>
            </Section>
        );
    }

    const directory = overview.directory;

    const doRotate = async () => {
        if (
            !window.confirm(
                'Rotate the SCIM token? The base URL and the token both change, and the current token stops working at once. You then enter the new ones at your identity provider, which sends its users and groups again. Members keep their access meanwhile.'
            )
        )
            return;
        const response: any = await rotate({ workspace_id: workspaceId });
        if (response.error) {
            toast({ description: errorMessage(response.error, 'Could not rotate the token.'), variant: 'destructive' });
            return;
        }
        setCredentials(response.data);
        if (response.data?.previousDirectoryDeleted === false) {
            toast({ description: 'The previous directory could not be deleted yet, so its token may still be accepted. Retry the clean-up below.', variant: 'destructive' });
        }
    };

    const doDelete = async () => {
        if (!window.confirm('Delete the directory? Members stay in the workspace with their current role and status, but your identity provider no longer adds, deactivates or updates them. Remove the SCIM app at your identity provider too.')) return;
        const response: any = await remove({ workspace_id: workspaceId });
        if (response.error) toast({ description: errorMessage(response.error, 'Could not delete the directory.'), variant: 'destructive' });
        else toast({ description: 'Directory deleted. Members were kept.' });
    };

    const doResync = async (force = false) => {
        const response: any = await resync({ workspace_id: workspaceId, force });
        const refusal = response.error?.data;
        if (!force && refusal?.code === 'mass_deprovision_refused') {
            const { wouldDeprovision, provisioned } = refusal.summary ?? {};
            if (window.confirm(`This resync would deactivate ${wouldDeprovision} of ${provisioned} members, more than the safety limit, so nothing was changed. Check your identity provider's assignments first. Deactivate them anyway?`)) {
                await doResync(true);
            }
            return;
        }
        if (response.error) toast({ description: errorMessage(response.error, 'Could not resync.'), variant: 'destructive' });
        else toast({ description: `Resynced ${response.data.summary.users ?? 0} users and ${response.data.summary.groups ?? 0} groups.` });
    };

    const doCleanup = async () => {
        const response: any = await cleanup({ workspace_id: workspaceId });
        if (response.error) toast({ description: errorMessage(response.error, 'The previous directory could not be deleted yet.'), variant: 'destructive' });
        else toast({ description: 'The previous directory was deleted.' });
    };

    return (
        <Section title={title} description={description}>
            {!overview.canManage && (
                <div role="note" className="flex items-start gap-2 rounded-md border border-[#D6E2F5] bg-[#F3F7FD] p-3 text-xs leading-relaxed text-black-700">
                    <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-brand-500" />
                    <span>Only the workspace owner can change directory sync. You can see its status.</span>
                </div>
            )}
            {credentials && <Credentials credentials={credentials} onDone={() => setCredentials(null)} />}

            {!directory ? (
                overview.canManage ? (
                    <CreateDirectoryForm overview={overview} workspaceId={workspaceId} onCreated={setCredentials} />
                ) : (
                    <p className="rounded-md border border-dashed border-black-200 px-3 py-3 text-xs text-black-600">No directory is connected.</p>
                )
            ) : (
                <>
                    <div className="flex flex-col gap-3 rounded-lg border border-black-200 bg-white p-4" data-testid="scim-directory">
                        <div className="flex flex-wrap items-start justify-between gap-3">
                            <div className="flex min-w-0 flex-col gap-1">
                                <div className="flex flex-wrap items-center gap-2">
                                    <Users className="h-4 w-4 shrink-0 text-[#0E8A5F]" />
                                    <span className="text-sm font-semibold text-black-900">{directory.typeLabel}</span>
                                    <span className="rounded bg-[#E7F6EE] px-1.5 py-0.5 text-[11px] font-medium text-[#0E8A5F]">Syncing</span>
                                </div>
                                <span className="text-xs text-black-500">{directory.lastEventAt ? `Last change ${formatTime(directory.lastEventAt)} (${directory.lastEventType})` : 'No change received yet.'}</span>
                                {directory.lastResyncAt && (
                                    <span className="text-xs text-black-500">
                                        {directory.lastResyncError
                                            ? `Last resync failed ${formatTime(directory.lastResyncAt)}: ${RESYNC_ERRORS[directory.lastResyncError] ?? RESYNC_ERRORS.resync_failed}`
                                            : `Last resync ${formatTime(directory.lastResyncAt)}`}
                                    </span>
                                )}
                            </div>
                            {overview.canManage && (
                                <div className="flex shrink-0 flex-wrap items-center gap-2">
                                    <Button size="sm" variant="v2Button" isLoading={isResyncing} onClick={() => doResync()} icon={<RefreshCw className="h-3.5 w-3.5" />}>
                                        Resync now
                                    </Button>
                                    <Button size="sm" variant="v2Button" isLoading={isRotating} onClick={doRotate}>
                                        Rotate token
                                    </Button>
                                    <Button size="sm" variant="dangerGhost" isLoading={isDeleting} onClick={doDelete}>
                                        Delete
                                    </Button>
                                </div>
                            )}
                        </div>
                        {directory.previousDirectoryPendingDelete && (
                            <div role="alert" className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-[#F2D9A6] bg-[#FDF8EC] px-3 py-2 text-xs text-black-800" data-testid="scim-stale-directory">
                                <span>The directory before the last rotation could not be deleted yet, so its old token may still be accepted. It is retried with every resync.</span>
                                {overview.canManage && (
                                    <Button size="sm" variant="v2Button" isLoading={isCleaning} onClick={doCleanup}>
                                        Retry
                                    </Button>
                                )}
                            </div>
                        )}
                        {directory.rotationGraceUntil && (
                            <p className="text-xs text-black-600">Token rotated: until {formatTime(directory.rotationGraceUntil)} a resync deactivates nobody, while your identity provider sends everyone to the new directory.</p>
                        )}
                        <CopyField label="SCIM base URL" value={directory.scimEndpoint} hint="The bearer token was shown when the directory was created; rotate it if you need a new one." />
                        <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                            {COUNT_LABELS.map(([key, label]) => (
                                <div key={key} className="bg-black-50 rounded-md px-3 py-2">
                                    <dt className="text-[11px] uppercase tracking-wide text-black-500">{label}</dt>
                                    <dd className={cn('text-lg font-semibold', key === 'failed' && (overview.counts[key] ?? 0) > 0 ? 'text-[#C43D3D]' : 'text-black-900')}>{overview.counts[key] ?? 0}</dd>
                                </div>
                            ))}
                        </dl>
                    </div>

                    {overview.issues.length > 0 && (
                        <div className="flex flex-col gap-2">
                            <h3 className="text-xs font-semibold text-black-800">Needs attention</h3>
                            <ul className="flex flex-col gap-1.5" data-testid="scim-issues">
                                {overview.issues.map((issue) => (
                                    <li key={`${issue.email}-${issue.reason}`} className={cn('flex flex-col gap-0.5 rounded-md border px-3 py-2 text-xs', issue.state === 'failed' ? 'border-[#F3D1D1] bg-[#FBEFEF]' : 'border-black-200 bg-white')}>
                                        <span className="break-all font-medium text-black-900">{issue.email || 'Unknown user'}</span>
                                        <span className="text-black-700">{issue.message}</span>
                                    </li>
                                ))}
                            </ul>
                        </div>
                    )}

                    <div className="flex flex-col gap-2">
                        <h3 className="text-xs font-semibold text-black-800">Groups and roles</h3>
                        <p className="max-w-[62ch] text-xs leading-relaxed text-black-600">
                            Give a group a workspace role; someone in several groups gets the highest. People in no mapped group get the role for new members ({roleLabel(overview.defaultRole)}, under Policy). The owner is never changed, and members you
                            invited by hand are left alone.
                        </p>
                        {overview.groups.length ? (
                            <table className="w-full text-left">
                                <thead>
                                    <tr className="text-[11px] uppercase tracking-wide text-black-500">
                                        <th className="pb-1 font-medium">Group</th>
                                        <th className="pb-1 font-medium">Members</th>
                                        <th className="pb-1 font-medium">Role</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {overview.groups.map((group) => (
                                        <GroupRow key={group.id} group={group} overview={overview} workspaceId={workspaceId} />
                                    ))}
                                </tbody>
                            </table>
                        ) : (
                            <p className="rounded-md border border-dashed border-black-200 px-3 py-3 text-xs text-black-600">No groups yet. Assign groups to the SCIM app at your identity provider (push groups).</p>
                        )}
                    </div>
                </>
            )}
        </Section>
    );
}
