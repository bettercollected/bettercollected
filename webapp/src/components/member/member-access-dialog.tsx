'use client';

import { useTranslation } from 'react-i18next';

import { WorkspaceMembersDto } from '@app/models/dtos/workspace-member-dto';
import { WorkspaceRole, roleLocale, toWorkspaceRole } from '@app/models/enums/workspace-role';
import { Button } from '@app/shadcn/components/ui/button';
import { Dialog, DialogContent } from '@app/shadcn/components/ui/dialog';
import { useGetMemberAccessQuery } from '@app/store/workspaces/form-access-api';
import { getFullNameFromUser } from '@app/utils/user-utils';

/**
 * "What can they open?": what one member holds beyond their workspace role, read-only: the teams they are in and
 * the access given to them on single forms (`GET .../members/{id}/access`). Owners and admins open every form
 * whatever is listed here, and a form's own Access settings are where this is changed.
 */
export default function MemberAccessDialog({ workspaceId, member, onClose }: { workspaceId: string; member: WorkspaceMembersDto; onClose: () => void }) {
    const { t } = useTranslation();
    const { data, isLoading, isError } = useGetMemberAccessQuery({ workspaceId, memberId: member.id });
    const name = getFullNameFromUser(member);
    const role = toWorkspaceRole(member.role) ?? toWorkspaceRole(member.roles?.[0]);
    const opensEverything = role === WorkspaceRole.OWNER || role === WorkspaceRole.ADMIN;
    const title = t('STAFF.TEAMS.ACCESS.TITLE', { name });

    return (
        <Dialog open onOpenChange={(open) => !open && onClose()}>
            <DialogContent title={title} className="max-h-[90vh] max-w-lg overflow-y-auto">
                <div className="flex flex-col gap-5" data-testid="member-access-dialog">
                    <div className="pr-8">
                        <h2 className="text-lg font-semibold text-black-900">{title}</h2>
                        <p className="mt-1 text-sm text-black-700">{opensEverything ? t('STAFF.TEAMS.ACCESS.OPENS_EVERYTHING') : t('STAFF.TEAMS.ACCESS.INTRO', { role: role ? t(roleLocale(role).name) : '' })}</p>
                    </div>

                    {isLoading ? (
                        <p role="status" className="text-sm text-black-600">
                            {t('STAFF.TEAMS.LOADING')}
                        </p>
                    ) : isError || !data ? (
                        <p role="alert" className="text-sm text-[#C43D3D]">
                            {t('STAFF.TEAMS.ACCESS.LOAD_FAILED')}
                        </p>
                    ) : (
                        <>
                            <section aria-labelledby="member-access-teams" className="flex flex-col gap-2">
                                <h3 id="member-access-teams" className="text-sm font-semibold text-black-900">
                                    {t('STAFF.TEAMS.ACCESS.TEAMS')} ({data.teams.length})
                                </h3>
                                {data.teams.length === 0 ? (
                                    <p className="text-sm text-black-700">{t('STAFF.TEAMS.ACCESS.NO_TEAMS')}</p>
                                ) : (
                                    <ul aria-labelledby="member-access-teams" className="flex flex-col divide-y divide-black-300 rounded border border-black-300">
                                        {data.teams.map((team) => (
                                            <li key={team.id} className="px-3 py-2 text-sm text-black-900">
                                                {team.name}
                                            </li>
                                        ))}
                                    </ul>
                                )}
                            </section>

                            <section aria-labelledby="member-access-grants" className="flex flex-col gap-2">
                                <h3 id="member-access-grants" className="text-sm font-semibold text-black-900">
                                    {t('STAFF.TEAMS.ACCESS.GRANTS')} ({data.grants.length})
                                </h3>
                                {data.grants.length === 0 ? (
                                    <p className="text-sm text-black-700">{t('STAFF.TEAMS.ACCESS.NO_GRANTS')}</p>
                                ) : (
                                    <ul aria-labelledby="member-access-grants" className="flex flex-col divide-y divide-black-300 rounded border border-black-300">
                                        {data.grants.map((grant) => (
                                            <li key={grant.id} className="flex flex-wrap items-center justify-between gap-2 px-3 py-2 text-sm text-black-900">
                                                <span className="min-w-0 truncate">{grant.formTitle || t('STAFF.TEAMS.ACCESS.A_FORM')}</span>
                                                <span className="text-black-700">
                                                    {t(roleLocale(grant.role).name)}
                                                    {grant.export ? `, ${t('STAFF.TEAMS.ACCESS.MAY_EXPORT')}` : ''}
                                                </span>
                                            </li>
                                        ))}
                                    </ul>
                                )}
                                <p className="text-xs text-black-600">{t('STAFF.TEAMS.ACCESS.NOTE')}</p>
                            </section>
                        </>
                    )}

                    <div className="flex justify-end border-t border-black-300 pt-4">
                        <Button type="button" variant="v2Button" className="min-h-11 md:min-h-10" onClick={onClose}>
                            {t('STAFF.TEAMS.CLOSE')}
                        </Button>
                    </div>
                </div>
            </DialogContent>
        </Dialog>
    );
}
