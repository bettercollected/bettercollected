'use client';

import { FormEvent, useId, useMemo, useState } from 'react';

import { UsersRound } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import TeamDirectoryGroups from '@app/components/member/team-directory-groups';
import { useWorkspacePermissions } from '@app/lib/hooks/use-workspace-permissions';
import { WorkspacePermission } from '@app/models/enums/workspace-permission';
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '@app/shadcn/components/ui/alert-dialog';
import { Button } from '@app/shadcn/components/ui/button';
import { Dialog, DialogContent } from '@app/shadcn/components/ui/dialog';
import { AppInput } from '@app/shadcn/components/ui/input';
import { useAppSelector } from '@app/store/hooks';
import {
    MAX_TEAMS,
    MAX_TEAM_MEMBERS,
    TeamDto,
    useAddTeamMemberMutation,
    useCreateTeamMutation,
    useDeleteTeamMutation,
    useGetTeamQuery,
    useGetTeamsQuery,
    useRemoveTeamMemberMutation,
    useRenameTeamMutation
} from '@app/store/workspaces/form-access-api';
import { useGetWorkspaceMembersQuery } from '@app/store/workspaces/members-n-invitations-api';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { formAccessErrorKey } from '@app/utils/form-access';
import { getFullNameFromUser } from '@app/utils/user-utils';

const selectClass = 'h-11 w-full min-w-0 rounded border border-black-400 bg-white px-3 py-0 text-sm text-black-900 disabled:cursor-not-allowed disabled:bg-black-200 md:h-10';

/**
 * Workspace, Members, Teams: named groups of members that a form's access can name in one step. Owners and admins
 * (members.manage) only, and only while the server has form-level access on; the tab is hidden under the same two
 * conditions. The server decides every limit and refusal: this page shows its words.
 */
export default function Teams() {
    const { t } = useTranslation();
    const { can, ready, formAccessEnabled } = useWorkspacePermissions();
    if (!ready) {
        return (
            <p role="status" className="py-6 text-sm text-black-600">
                {t('STAFF.TEAMS.LOADING')}
            </p>
        );
    }
    if (!can(WorkspacePermission.MEMBERS_MANAGE)) return <p className="py-6 text-sm text-black-700">{t('STAFF.TEAMS.ONLY_ADMINS')}</p>;
    if (!formAccessEnabled) return <p className="py-6 text-sm text-black-700">{t('STAFF.TEAMS.TURNED_OFF')}</p>;
    return <TeamsList />;
}

function TeamsList() {
    const { t } = useTranslation();
    const workspace = useAppSelector(selectWorkspace);
    const workspaceId = workspace?.id as string;
    const teams = useGetTeamsQuery(workspaceId, { skip: !workspaceId });
    const [createTeam, { isLoading: creating }] = useCreateTeamMutation();
    const [name, setName] = useState('');
    const [error, setError] = useState<string | null>(null);
    const [notice, setNotice] = useState<string | null>(null);
    const [openTeam, setOpenTeam] = useState<TeamDto | null>(null);
    const id = useId();

    const list = teams.data ?? [];
    const full = list.length >= MAX_TEAMS;

    const create = async (event: FormEvent) => {
        event.preventDefault();
        const value = name.trim();
        if (!value) return;
        setError(null);
        setNotice(null);
        const response = await createTeam({ workspaceId, name: value });
        if ('error' in response && response.error) {
            setError(t(formAccessErrorKey(response.error), { max: MAX_TEAMS }));
            return;
        }
        setName('');
        setNotice(t('STAFF.TEAMS.CREATED'));
    };

    return (
        <div className="flex w-full max-w-[720px] flex-col gap-6">
            <div className="flex flex-col gap-1">
                <div className="flex items-baseline justify-between gap-3">
                    <h2 className="body1">{t('STAFF.TEAMS.TITLE')}</h2>
                    <span className="text-xs text-black-600">{t('STAFF.TEAMS.COUNT', { count: list.length, max: MAX_TEAMS })}</span>
                </div>
                <p className="max-w-[62ch] text-sm leading-relaxed text-black-700">{t('STAFF.TEAMS.INTRO')}</p>
            </div>

            <form onSubmit={create} noValidate className="flex flex-col gap-2">
                <label htmlFor={`${id}-name`} className="text-sm font-medium text-black-700">
                    {t('STAFF.TEAMS.NEW')}
                </label>
                <div className="flex flex-col gap-2 sm:flex-row">
                    <AppInput
                        id={`${id}-name`}
                        value={name}
                        maxLength={80}
                        autoComplete="off"
                        placeholder={t('STAFF.TEAMS.NAME_PLACEHOLDER')}
                        aria-invalid={error ? true : undefined}
                        aria-describedby={error ? `${id}-error` : full ? `${id}-limit` : undefined}
                        disabled={full}
                        className="h-11 w-full md:h-10"
                        onChange={(event) => {
                            setName(event.target.value);
                            setError(null);
                            setNotice(null);
                        }}
                    />
                    <Button type="submit" variant="primary" className="min-h-11 shrink-0 md:min-h-10" disabled={creating || full || !name.trim()}>
                        {t('STAFF.TEAMS.CREATE')}
                    </Button>
                </div>
                {full && (
                    <p id={`${id}-limit`} className="text-sm text-black-700">
                        {t('STAFF.TEAMS.LIMIT', { max: MAX_TEAMS })}
                    </p>
                )}
                {error && (
                    <p id={`${id}-error`} role="alert" className="text-sm text-[#C43D3D]">
                        {error}
                    </p>
                )}
                <p role="status" className="min-h-5 text-sm text-black-600">
                    {notice}
                </p>
            </form>

            {teams.isLoading ? (
                <p role="status" className="text-sm text-black-600">
                    {t('STAFF.TEAMS.LOADING')}
                </p>
            ) : teams.isError ? (
                <p role="alert" className="text-sm text-[#C43D3D]">
                    {t('STAFF.TEAMS.LOAD_FAILED')}
                </p>
            ) : list.length === 0 ? (
                <p className="text-sm text-black-700">{t('STAFF.TEAMS.EMPTY')}</p>
            ) : (
                <ul aria-label={t('STAFF.TEAMS.LIST_LABEL')} className="flex flex-col divide-y divide-black-300 rounded border border-black-300 bg-white">
                    {list.map((team) => (
                        <li key={team.id} className="flex items-center justify-between gap-3 px-4 py-3">
                            <div className="flex min-w-0 items-center gap-3">
                                <UsersRound className="h-4 w-4 shrink-0 text-black-600" aria-hidden="true" />
                                <div className="flex min-w-0 flex-col">
                                    <span className="truncate text-sm font-medium text-black-900">{team.name}</span>
                                    <span className="text-xs text-black-600">
                                        {t('STAFF.TEAMS.PEOPLE', { count: team.memberCount })}
                                        {team.source && team.source !== 'manual' ? ` · ${t('STAFF.TEAMS.MANAGED')}` : ''}
                                        {team.linkedGroups ? ` · ${t('STAFF.TEAMS.LINKED', { count: team.linkedGroups })}` : ''}
                                    </span>
                                </div>
                            </div>
                            <Button type="button" variant="v2Button" className="min-h-11 shrink-0 md:min-h-10" aria-label={t('STAFF.TEAMS.MANAGE_ARIA', { name: team.name })} onClick={() => setOpenTeam(team)}>
                                {t('STAFF.TEAMS.MANAGE')}
                            </Button>
                        </li>
                    ))}
                </ul>
            )}

            <TeamDirectoryGroups workspaceId={workspaceId} teams={list} />

            {openTeam && <TeamDialog workspaceId={workspaceId} team={openTeam} onClose={() => setOpenTeam(null)} />}
        </div>
    );
}

function TeamDialog({ workspaceId, team, onClose }: { workspaceId: string; team: TeamDto; onClose: () => void }) {
    const { t } = useTranslation();
    const id = useId();
    const detail = useGetTeamQuery({ workspaceId, teamId: team.id });
    const members = useGetWorkspaceMembersQuery({ workspaceId });
    const [rename, { isLoading: renaming }] = useRenameTeamMutation();
    const [removeTeam, { isLoading: deleting }] = useDeleteTeamMutation();
    const [addMember, { isLoading: adding }] = useAddTeamMemberMutation();
    const [removeMember, { isLoading: removingMember }] = useRemoveTeamMemberMutation();
    const [name, setName] = useState<string | null>(null);
    const [pick, setPick] = useState('');
    const [confirmDelete, setConfirmDelete] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [notice, setNotice] = useState<string | null>(null);

    const current = detail.data;
    const teamName = current?.name ?? team.name;
    const shownName = name ?? teamName;
    const inTeam = useMemo(() => new Set((current?.members ?? []).map((member) => member.userId)), [current?.members]);
    // only active members can be added (the server refuses a deactivated one)
    const candidates = useMemo(() => (members.data ?? []).filter((member) => !member.disabled && !member.accountDeleted && !inTeam.has(member.id)), [members.data, inTeam]);
    const busy = renaming || deleting || adding || removingMember;
    const unknownPerson = t('STAFF.TEAMS.UNKNOWN_PERSON');

    const fail = (response: { error?: unknown }) => {
        setError(t(formAccessErrorKey(response.error), { max: MAX_TEAM_MEMBERS }));
        setNotice(null);
    };

    const saveName = async (event: FormEvent) => {
        event.preventDefault();
        const value = (name ?? '').trim();
        if (!value || value === current?.name) return;
        setError(null);
        const response = await rename({ workspaceId, teamId: team.id, name: value });
        if ('error' in response && response.error) return fail(response);
        setName(null);
        setNotice(t('STAFF.TEAMS.SAVED'));
    };

    const add = async (event: FormEvent) => {
        event.preventDefault();
        if (!pick) return;
        setError(null);
        const response = await addMember({ workspaceId, teamId: team.id, memberId: pick });
        if ('error' in response && response.error) return fail(response);
        setPick('');
        setNotice(t('STAFF.TEAMS.SAVED'));
    };

    const remove = async (memberId: string) => {
        setError(null);
        const response = await removeMember({ workspaceId, teamId: team.id, memberId });
        if ('error' in response && response.error) return fail(response);
        setNotice(t('STAFF.TEAMS.SAVED'));
    };

    const confirmDeletion = async () => {
        setConfirmDelete(false);
        setError(null);
        const response = await removeTeam({ workspaceId, teamId: team.id });
        if ('error' in response && response.error) return fail(response);
        onClose();
    };

    return (
        <>
            <Dialog open onOpenChange={(open) => !open && onClose()}>
                <DialogContent title={teamName} className="max-h-[90vh] max-w-xl overflow-y-auto">
                    <div className="flex flex-col gap-5">
                        <div className="pr-8">
                            <h2 className="text-lg font-semibold text-black-900">{teamName}</h2>
                            <p className="mt-1 text-sm text-black-700">{current ? t('STAFF.TEAMS.USED_ON', { count: current.formCount }) : t('STAFF.TEAMS.LOADING')}</p>
                        </div>

                        <form onSubmit={saveName} noValidate className="flex flex-col gap-2">
                            <label htmlFor={`${id}-rename`} className="text-sm font-medium text-black-700">
                                {t('STAFF.TEAMS.RENAME_LABEL')}
                            </label>
                            <div className="flex flex-col gap-2 sm:flex-row">
                                <AppInput id={`${id}-rename`} value={shownName} maxLength={80} autoComplete="off" className="h-11 w-full md:h-10" onChange={(event) => setName(event.target.value)} />
                                <Button type="submit" variant="v2Button" className="min-h-11 shrink-0 md:min-h-10" disabled={busy || !shownName.trim() || shownName.trim() === teamName}>
                                    {t('STAFF.TEAMS.RENAME')}
                                </Button>
                            </div>
                        </form>

                        <section aria-labelledby={`${id}-members`} className="flex flex-col gap-2">
                            <h3 id={`${id}-members`} className="text-sm font-semibold text-black-900">
                                {t('STAFF.TEAMS.MEMBERS_TITLE')} ({current?.members.length ?? team.memberCount})
                            </h3>
                            {detail.isLoading ? (
                                <p role="status" className="text-sm text-black-600">
                                    {t('STAFF.TEAMS.LOADING')}
                                </p>
                            ) : detail.isError ? (
                                <p role="alert" className="text-sm text-[#C43D3D]">
                                    {t('STAFF.TEAMS.LOAD_FAILED')}
                                </p>
                            ) : (current?.members.length ?? 0) === 0 ? (
                                <p className="text-sm text-black-700">{t('STAFF.TEAMS.NO_MEMBERS')}</p>
                            ) : (
                                <ul aria-labelledby={`${id}-members`} className="flex max-h-56 flex-col divide-y divide-black-300 overflow-y-auto rounded border border-black-300">
                                    {current!.members.map((member) => {
                                        const label = member.name || unknownPerson;
                                        return (
                                            <li key={member.userId} className="flex items-center justify-between gap-3 px-3 py-2">
                                                <span className="min-w-0 truncate text-sm text-black-900">{label}</span>
                                                {member.viaDirectory ? (
                                                    <span className="shrink-0 text-xs text-black-600">{t('STAFF.TEAMS.VIA_DIRECTORY')}</span>
                                                ) : (
                                                    <>
                                                        {member.alsoViaDirectory && <span className="shrink-0 text-xs text-black-600">{t('STAFF.TEAMS.ALSO_VIA_DIRECTORY')}</span>}
                                                        <Button type="button" variant="v2Button" className="min-h-11 shrink-0 md:min-h-9" disabled={busy} aria-label={t('STAFF.TEAMS.REMOVE_MEMBER_ARIA', { name: label, team: teamName })} onClick={() => remove(member.userId)}>
                                                        {t('STAFF.TEAMS.REMOVE')}
                                                    </Button>
                                                    </>
                                                )}
                                            </li>
                                        );
                                    })}
                                </ul>
                            )}

                            {current?.membersTruncated && <p className="text-xs text-black-600">{t('STAFF.TEAMS.MEMBERS_TRUNCATED', { shown: current.members.length, total: current.memberCount })}</p>}

                            <form onSubmit={add} noValidate className="mt-2 flex flex-col gap-2">
                                <label htmlFor={`${id}-add`} className="text-sm font-medium text-black-700">
                                    {t('STAFF.TEAMS.ADD_LABEL')}
                                </label>
                                <div className="flex flex-col gap-2 sm:flex-row">
                                    <select id={`${id}-add`} className={selectClass} value={pick} onChange={(event) => setPick(event.target.value)} disabled={busy || candidates.length === 0} aria-describedby={`${id}-add-note`}>
                                        <option value="">{t('STAFF.TEAMS.ADD_PLACEHOLDER')}</option>
                                        {candidates.map((member) => (
                                            <option key={member.id} value={member.id}>
                                                {getFullNameFromUser(member)}
                                            </option>
                                        ))}
                                    </select>
                                    <Button type="submit" variant="primary" className="min-h-11 shrink-0 md:min-h-10" disabled={busy || !pick}>
                                        {t('STAFF.TEAMS.ADD_BUTTON')}
                                    </Button>
                                </div>
                                <p id={`${id}-add-note`} className="text-xs text-black-600">
                                    {candidates.length === 0 && !members.isLoading ? t('STAFF.TEAMS.NONE_TO_ADD') : t('STAFF.TEAMS.ACTIVE_ONLY', { max: MAX_TEAM_MEMBERS })}
                                </p>
                            </form>
                        </section>

                        {error && (
                            <p role="alert" className="text-sm text-[#C43D3D]">
                                {error}
                            </p>
                        )}
                        <p role="status" className="min-h-5 text-sm text-black-600">
                            {notice}
                        </p>

                        <div className="flex justify-between gap-3 border-t border-black-300 pt-4">
                            <Button type="button" variant="dangerGhost" className="min-h-11 md:min-h-10" disabled={busy || !current} onClick={() => setConfirmDelete(true)}>
                                {t('STAFF.TEAMS.DELETE')}
                            </Button>
                            <Button type="button" variant="v2Button" className="min-h-11 md:min-h-10" onClick={onClose}>
                                {t('STAFF.TEAMS.CLOSE')}
                            </Button>
                        </div>
                    </div>
                </DialogContent>
            </Dialog>

            <AlertDialog open={confirmDelete} onOpenChange={setConfirmDelete}>
                <AlertDialogContent>
                    <AlertDialogHeader>
                        <AlertDialogTitle>{t('STAFF.TEAMS.DELETE_TITLE', { name: teamName })}</AlertDialogTitle>
                        <AlertDialogDescription>{t('STAFF.TEAMS.DELETE_BODY', { count: current?.formCount ?? 0 })}</AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                        <AlertDialogCancel>{t('STAFF.FORM_ACCESS.CANCEL')}</AlertDialogCancel>
                        <AlertDialogAction
                            onClick={(event) => {
                                event.preventDefault();
                                confirmDeletion();
                            }}
                        >
                            {t('STAFF.TEAMS.DELETE')}
                        </AlertDialogAction>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>
        </>
    );
}
