'use client';

import { useId, useState } from 'react';

import { useTranslation } from 'react-i18next';

import { useWorkspacePermissions } from '@app/lib/hooks/use-workspace-permissions';
import { WorkspacePermission } from '@app/models/enums/workspace-permission';
import { useGetWorkspaceScimQuery } from '@app/store/workspaces/api';
import { useClearScimGroupTeamMutation, useSetScimGroupTeamMutation } from '@app/store/workspaces/form-access-api';
import type { TeamDto } from '@app/store/workspaces/form-access-api';
import { formAccessErrorKey } from '@app/utils/form-access';

const selectClass = 'h-11 w-full min-w-0 rounded border border-black-400 bg-white px-3 py-0 text-sm text-black-900 disabled:cursor-not-allowed disabled:bg-black-200 md:h-10 sm:w-64';

/**
 * Workspace, Members, Teams: which team each group of the workspace's directory (SCIM) feeds. Only the owner changes it,
 * so nobody else sees the section; it is also absent while there is no directory. A group is in one team, a team may
 * take several groups. The people in a linked group are in the team while the directory says so: nothing is copied, so
 * removing someone in the directory takes them out of the team on the next request. The server decides every refusal.
 */
export default function TeamDirectoryGroups({ workspaceId, teams }: { workspaceId: string; teams: TeamDto[] }) {
    const { t } = useTranslation();
    const { can } = useWorkspacePermissions();
    const id = useId();
    // viewing the directory needs security.manage (owners and admins); a person without it never asks
    const overview = useGetWorkspaceScimQuery(workspaceId, { skip: !workspaceId || !can(WorkspacePermission.SECURITY_MANAGE) });
    const [setTeam, { isLoading: linking }] = useSetScimGroupTeamMutation();
    const [clearTeam, { isLoading: unlinking }] = useClearScimGroupTeamMutation();
    const [error, setError] = useState<string | null>(null);
    const [notice, setNotice] = useState<string | null>(null);

    const data = overview.data;
    if (!data || !data.available || !data.directory || !data.canManage) return null;

    const busy = linking || unlinking;
    const groups = data.groups ?? [];

    const change = async (groupId: string, teamId: string) => {
        setError(null);
        setNotice(null);
        const response = teamId ? await setTeam({ workspaceId, groupId, teamId }) : await clearTeam({ workspaceId, groupId });
        if ('error' in response && response.error) {
            setError(t(formAccessErrorKey(response.error)));
            return;
        }
        setNotice(t('STAFF.TEAMS.DIRECTORY_SAVED'));
    };

    return (
        <section aria-labelledby={`${id}-title`} className="flex flex-col gap-3 border-t border-black-300 pt-6">
            <div className="flex flex-col gap-1">
                <h2 id={`${id}-title`} className="body1">
                    {t('STAFF.TEAMS.DIRECTORY_TITLE')}
                </h2>
                <p className="max-w-[62ch] text-sm leading-relaxed text-black-700">{t('STAFF.TEAMS.DIRECTORY_INTRO')}</p>
                <p className="text-xs text-black-600">{t('STAFF.TEAMS.DIRECTORY_RULE')}</p>
            </div>

            {groups.length === 0 ? (
                <p className="text-sm text-black-700">{t('STAFF.TEAMS.DIRECTORY_EMPTY')}</p>
            ) : (
                <ul aria-label={t('STAFF.TEAMS.DIRECTORY_TITLE')} className="flex flex-col divide-y divide-black-300 rounded border border-black-300 bg-white">
                    {groups.map((group) => {
                        // a link to a team that is not in the list (deleted meanwhile) shows as not linked
                        const linked = teams.some((team) => team.id === group.teamId) ? (group.teamId as string) : '';
                        return (
                            <li key={group.id} className="flex flex-col gap-2 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
                                <div className="flex min-w-0 flex-col">
                                    <span className="truncate text-sm font-medium text-black-900">{group.name}</span>
                                    <span className="text-xs text-black-600">{t('STAFF.TEAMS.PEOPLE', { count: group.members })}</span>
                                </div>
                                <div className="flex flex-col gap-1">
                                    <label htmlFor={`${id}-${group.id}`} className="sr-only">
                                        {t('STAFF.TEAMS.DIRECTORY_TEAM_LABEL', { name: group.name })}
                                    </label>
                                    <select id={`${id}-${group.id}`} className={selectClass} value={linked} disabled={busy} onChange={(event) => change(group.id, event.target.value)}>
                                        <option value="">{t('STAFF.TEAMS.DIRECTORY_NOT_LINKED')}</option>
                                        {teams.map((team) => (
                                            <option key={team.id} value={team.id}>
                                                {team.name}
                                            </option>
                                        ))}
                                    </select>
                                </div>
                            </li>
                        );
                    })}
                </ul>
            )}

            {error && (
                <p role="alert" className="text-sm text-[#C43D3D]">
                    {error}
                </p>
            )}
            <p role="status" className="min-h-5 text-sm text-black-600">
                {notice}
            </p>
        </section>
    );
}
