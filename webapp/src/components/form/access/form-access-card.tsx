'use client';

import { useEffect, useId, useMemo, useRef, useState } from 'react';

import { Lock, UserRound, UsersRound } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import { GroupHeading } from '@app/components/dashboard/form-settings';
import { useWorkspacePermissions } from '@app/lib/hooks/use-workspace-permissions';
import { WorkspacePermission } from '@app/models/enums/workspace-permission';
import { WorkspaceRole, memberRole, roleLocale } from '@app/models/enums/workspace-role';
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '@app/shadcn/components/ui/alert-dialog';
import { Button } from '@app/shadcn/components/ui/button';
import { Label } from '@app/shadcn/components/ui/label';
import { RadioGroup, RadioGroupItem } from '@app/shadcn/components/ui/radio-group';
import { selectAuth } from '@app/store/auth/slice';
import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { FormAccessDto, FormAccessMode, FormGrantDto, GrantRole, useDeleteFormGrantMutation, useGetFormAccessQuery, useGetTeamsQuery, usePutFormGrantMutation, useSetFormAccessModeMutation } from '@app/store/workspaces/form-access-api';
import { useGetWorkspaceMembersQuery } from '@app/store/workspaces/members-n-invitations-api';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { exportFlagApplies, formAccessErrorKey, grantableRoles } from '@app/utils/form-access';
import { getFullNameFromUser } from '@app/utils/user-utils';

const selectClass = 'h-11 w-full min-w-0 rounded border border-black-400 bg-white px-3 py-0 text-sm text-black-900 disabled:cursor-not-allowed disabled:bg-black-200 disabled:text-black-600 md:h-10';

/**
 * Settings, Access: "Who on your team can open this form". The staff question (which members of the workspace open
 * this form in the dashboard), kept apart from the respondent visibility below it. Shown only while the server has
 * form-level access on (`formAccessEnabled`); with it off nothing renders and nothing is requested. Every rule is
 * the server's: this card offers what the caller's permissions suggest and shows the server's refusals as sentences.
 */
export default function FormAccessCard() {
    const { formAccessEnabled } = useWorkspacePermissions();
    const workspace = useAppSelector(selectWorkspace);
    const form = useAppSelector(selectForm);
    if (!formAccessEnabled || !workspace?.id || !form?.formId) return null;
    return <AccessCard workspaceId={workspace.id} formId={form.formId} hidden={!!form?.settings?.hidden} />;
}

function AccessCard({ workspaceId, formId, hidden }: { workspaceId: string; formId: string; hidden: boolean }) {
    const { t } = useTranslation();
    const id = useId();
    const { data, isLoading, isError, refetch } = useGetFormAccessQuery({ workspaceId, formId });
    const [setMode, { isLoading: savingMode }] = useSetFormAccessModeMutation();
    const [pendingMode, setPendingMode] = useState<FormAccessMode | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [notice, setNotice] = useState<string | null>(null);

    // A Private form counts as restricted until a mode is chosen: when the respondent visibility changes, ask again.
    const first = useRef(true);
    useEffect(() => {
        if (first.current) {
            first.current = false;
            return;
        }
        refetch();
    }, [hidden, refetch]);

    if (data && !data.enabled) return null;

    const restricted = !!data?.restricted;
    const canManage = !!data?.canManage;
    const mode: FormAccessMode = restricted ? 'restricted' : 'workspace';

    const confirmMode = async () => {
        const next = pendingMode;
        setPendingMode(null);
        if (!next) return;
        setError(null);
        setNotice(null);
        const response = await setMode({ workspaceId, formId, mode: next });
        if ('error' in response && response.error) setError(t(formAccessErrorKey(response.error)));
        else setNotice(t('STAFF.FORM_ACCESS.SAVED'));
    };

    return (
        <section aria-labelledby={`${id}-title`} data-testid="form-access-card" className="flex flex-col gap-3">
            <div>
                <GroupHeading>
                    <span id={`${id}-title`}>{t('STAFF.FORM_ACCESS.TITLE')}</span>
                </GroupHeading>
                <p className="max-w-[62ch] text-sm leading-relaxed text-black-700">{t('STAFF.FORM_ACCESS.INTRO')}</p>
            </div>

            <div className="flex flex-col gap-4 rounded-lg border border-black-300 bg-white p-5">
                {isLoading ? (
                    <p role="status" className="text-sm text-black-600">
                        {t('STAFF.FORM_ACCESS.LOADING')}
                    </p>
                ) : isError || !data ? (
                    <p role="alert" className="text-sm text-[#C43D3D]">
                        {t('STAFF.FORM_ACCESS.LOAD_FAILED')}
                    </p>
                ) : (
                    <>
                        <RadioGroup aria-labelledby={`${id}-title`} className="flex flex-col gap-4" value={mode} disabled={!canManage || savingMode} onValueChange={(value) => value !== mode && setPendingMode(value as FormAccessMode)}>
                            <ModeOption id={`${id}-open`} value="workspace" title={t('STAFF.FORM_ACCESS.MODE_OPEN')} description={t('STAFF.FORM_ACCESS.MODE_OPEN_DESC')} disabled={!canManage || savingMode} />
                            <ModeOption id={`${id}-restricted`} value="restricted" icon={<Lock className="h-4 w-4" aria-hidden="true" />} title={t('STAFF.FORM_ACCESS.MODE_RESTRICTED')} description={t('STAFF.FORM_ACCESS.MODE_RESTRICTED_DESC')} disabled={!canManage || savingMode} />
                        </RadioGroup>
                        <p className="text-sm text-black-700">{t('STAFF.FORM_ACCESS.ALWAYS')}</p>
                        {!canManage && (
                            <p role="note" className="rounded border border-black-300 bg-black-100 px-3 py-2 text-sm text-black-800">
                                {t('STAFF.FORM_ACCESS.READ_ONLY')}
                            </p>
                        )}
                        {error && (
                            <p role="alert" className="text-sm text-[#C43D3D]">
                                {error}
                            </p>
                        )}
                        <p role="status" className="text-sm text-black-600">
                            {notice}
                        </p>
                        {data.grants && <GrantsSection workspaceId={workspaceId} formId={formId} access={data} setError={setError} setNotice={setNotice} />}
                    </>
                )}
            </div>

            <AlertDialog open={!!pendingMode} onOpenChange={(open) => !open && setPendingMode(null)}>
                <AlertDialogContent>
                    <AlertDialogHeader>
                        <AlertDialogTitle>{pendingMode === 'restricted' ? t('STAFF.FORM_ACCESS.CONFIRM_RESTRICT_TITLE') : t('STAFF.FORM_ACCESS.CONFIRM_OPEN_TITLE')}</AlertDialogTitle>
                        <AlertDialogDescription>{pendingMode === 'restricted' ? t('STAFF.FORM_ACCESS.CONFIRM_RESTRICT_BODY') : t('STAFF.FORM_ACCESS.CONFIRM_OPEN_BODY')}</AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                        <AlertDialogCancel>{t('STAFF.FORM_ACCESS.CANCEL')}</AlertDialogCancel>
                        <AlertDialogAction
                            onClick={(event) => {
                                event.preventDefault();
                                confirmMode();
                            }}
                        >
                            {pendingMode === 'restricted' ? t('STAFF.FORM_ACCESS.CONFIRM_RESTRICT') : t('STAFF.FORM_ACCESS.CONFIRM_OPEN')}
                        </AlertDialogAction>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>
        </section>
    );
}

function ModeOption({ id, value, title, description, icon, disabled }: { id: string; value: string; title: string; description: string; icon?: React.ReactNode; disabled: boolean }) {
    return (
        <div className="flex flex-col">
            <div className="flex items-center gap-2">
                <RadioGroupItem value={value} id={id} aria-describedby={`${id}-desc`} disabled={disabled} className="shrink-0" />
                <Label htmlFor={id} className="flex min-h-6 cursor-pointer items-center gap-1.5 text-sm font-medium text-black-900">
                    {icon}
                    {title}
                </Label>
            </div>
            <span id={`${id}-desc`} className="ml-6 mt-1 text-sm text-black-700">
                {description}
            </span>
        </div>
    );
}

type Subject = { key: string; type: 'user' | 'group'; id: string; label: string };

function GrantsSection({ workspaceId, formId, access, setError, setNotice }: { workspaceId: string; formId: string; access: FormAccessDto; setError: (value: string | null) => void; setNotice: (value: string | null) => void }) {
    const { t, i18n } = useTranslation();
    const id = useId();
    const auth = useAppSelector(selectAuth);
    const { can } = useWorkspacePermissions();
    // Owners and admins hold members.manage: they alone may list the members and teams to choose from.
    const isAdmin = can(WorkspacePermission.MEMBERS_MANAGE);
    const canManage = !!access.canManage;
    const grants: FormGrantDto[] = access.grants ?? [];
    const roles = useMemo(() => grantableRoles(access.myPermissions), [access.myPermissions]);
    const [putGrant, { isLoading: putting }] = usePutFormGrantMutation();
    const [deleteGrant, { isLoading: deleting }] = useDeleteFormGrantMutation();
    const [removing, setRemoving] = useState<FormGrantDto | null>(null);
    const busy = putting || deleting;

    const members = useGetWorkspaceMembersQuery({ workspaceId }, { skip: !canManage || !isAdmin });
    const teams = useGetTeamsQuery(workspaceId, { skip: !canManage || !isAdmin });

    const taken = useMemo(() => new Set(grants.map((grant: FormGrantDto) => `${grant.subjectType}:${grant.subjectId}`)), [grants]);
    const subjects = useMemo<Subject[]>(() => {
        const people: Subject[] = (members.data ?? [])
            .filter((member) => {
                const role = memberRole(member);
                // owners and admins always have access; a deactivated or deleted account, a privacy officer and oneself cannot be given any
                return !member.disabled && !member.accountDeleted && member.id !== auth?.id && role !== WorkspaceRole.OWNER && role !== WorkspaceRole.ADMIN && role !== WorkspaceRole.PRIVACY_OFFICER;
            })
            .map((member) => ({ key: `user:${member.id}`, type: 'user' as const, id: member.id, label: getFullNameFromUser(member) }));
        const groups: Subject[] = (teams.data ?? []).map((team) => ({ key: `group:${team.id}`, type: 'group' as const, id: team.id, label: team.name }));
        return [...people, ...groups].filter((subject) => !taken.has(subject.key));
    }, [members.data, teams.data, taken, auth?.id]);

    const [subjectKey, setSubjectKey] = useState('');
    const [role, setRole] = useState<GrantRole | ''>('');
    const [allowExport, setAllowExport] = useState(false);
    const chosenRole: GrantRole | '' = role && roles.includes(role) ? role : (roles.includes('REVIEWER') ? 'REVIEWER' : (roles[0] ?? ''));
    const subject = subjects.find((item) => item.key === subjectKey);

    const save = async (request: { subjectType: 'user' | 'group'; subjectId: string; role: GrantRole; export: boolean }) => {
        setError(null);
        setNotice(null);
        const response = await putGrant({ workspaceId, formId, grant: request });
        if ('error' in response && response.error) {
            setError(t(formAccessErrorKey(response.error), { max: 20 }));
            return false;
        }
        setNotice(t('STAFF.FORM_ACCESS.SAVED'));
        return true;
    };

    const add = async (event: React.FormEvent) => {
        event.preventDefault();
        if (!subject || !chosenRole) return;
        const ok = await save({ subjectType: subject.type, subjectId: subject.id, role: chosenRole, export: allowExport && isAdmin && exportFlagApplies(chosenRole) });
        if (ok) {
            setSubjectKey('');
            setAllowExport(false);
        }
    };

    const confirmRemove = async () => {
        const grant = removing;
        setRemoving(null);
        if (!grant) return;
        setError(null);
        setNotice(null);
        const response = await deleteGrant({ workspaceId, formId, grantId: grant.id });
        if ('error' in response && response.error) setError(t(formAccessErrorKey(response.error)));
        else setNotice(t('STAFF.FORM_ACCESS.SAVED'));
    };

    const nameOf = (grant: FormGrantDto) => grant.name || t(grant.subjectType === 'group' ? 'STAFF.FORM_ACCESS.UNKNOWN_TEAM' : 'STAFF.FORM_ACCESS.UNKNOWN_PERSON');

    return (
        <div className="flex flex-col gap-4 border-t border-black-300 pt-5">
            <h4 id={`${id}-list`} className="text-sm font-semibold text-black-900">
                {t('STAFF.FORM_ACCESS.LIST_TITLE')} ({grants.length})
            </h4>
            {grants.length === 0 ? (
                <p className="text-sm text-black-700">{access.restricted ? t('STAFF.FORM_ACCESS.LIST_EMPTY_RESTRICTED') : t('STAFF.FORM_ACCESS.LIST_EMPTY_OPEN')}</p>
            ) : (
                <ul aria-labelledby={`${id}-list`} className="flex flex-col divide-y divide-black-300 rounded border border-black-300">
                    {grants.map((grant: FormGrantDto) => {
                        const name = nameOf(grant);
                        // owners and admins alone change a grant that allows exporting
                        const locked = !canManage || busy || (grant.export && !isAdmin);
                        const offered = Array.from(new Set<GrantRole>([...roles, grant.role]));
                        return (
                            <li key={grant.id} className="flex flex-col gap-3 px-3 py-3 md:flex-row md:items-center md:justify-between md:gap-4">
                                <div className="flex min-w-0 items-center gap-2">
                                    {grant.subjectType === 'group' ? <UsersRound className="h-4 w-4 shrink-0 text-black-600" aria-hidden="true" /> : <UserRound className="h-4 w-4 shrink-0 text-black-600" aria-hidden="true" />}
                                    <div className="flex min-w-0 flex-col">
                                        <span className="truncate text-sm font-medium text-black-900">
                                            <span className="sr-only">{t(grant.subjectType === 'group' ? 'STAFF.FORM_ACCESS.TEAM_PREFIX' : 'STAFF.FORM_ACCESS.PERSON_PREFIX')} </span>
                                            {name}
                                        </span>
                                        <span className="flex flex-wrap gap-x-2 text-xs text-black-600">
                                            {grant.subjectType === 'group' && <span>{t('STAFF.FORM_ACCESS.TEAM')}</span>}
                                            {grant.disabled && <span className="font-medium text-[#C43D3D]">{t('STAFF.FORM_ACCESS.MEMBER_DISABLED')}</span>}
                                            {grant.createdAt && <span>{t('STAFF.FORM_ACCESS.ADDED', { date: formatDay(grant.createdAt, i18n.language) })}</span>}
                                        </span>
                                    </div>
                                </div>
                                <div className="flex flex-wrap items-center gap-3 md:flex-nowrap">
                                    <select
                                        aria-label={t('STAFF.FORM_ACCESS.ROLE_ARIA', { name })}
                                        className={`${selectClass} md:w-36`}
                                        value={grant.role}
                                        disabled={locked}
                                        onChange={(event) => {
                                            const next = event.target.value as GrantRole;
                                            save({ subjectType: grant.subjectType, subjectId: grant.subjectId, role: next, export: grant.export && exportFlagApplies(next) });
                                        }}
                                    >
                                        {offered.map((item) => (
                                            <option key={item} value={item}>
                                                {t(roleLocale(item).name)}
                                            </option>
                                        ))}
                                    </select>
                                    {exportFlagApplies(grant.role) ? (
                                        <label className="flex min-h-11 items-center gap-2 text-sm text-black-800 md:min-h-8 md:w-52">
                                            <input
                                                type="checkbox"
                                                className="h-5 w-5 shrink-0"
                                                aria-label={t('STAFF.FORM_ACCESS.EXPORT_ARIA', { name })}
                                                checked={grant.export}
                                                disabled={locked || !isAdmin}
                                                onChange={(event) => save({ subjectType: grant.subjectType, subjectId: grant.subjectId, role: grant.role, export: event.target.checked })}
                                            />
                                            {t('STAFF.FORM_ACCESS.EXPORT')}
                                        </label>
                                    ) : (
                                        <span className="text-sm text-black-600 md:w-52">{t('STAFF.FORM_ACCESS.EXPORT_INCLUDED')}</span>
                                    )}
                                    {canManage && (
                                        <Button type="button" variant="v2Button" className="min-h-11 md:min-h-10" disabled={locked} aria-label={t('STAFF.FORM_ACCESS.REMOVE_ARIA', { name })} onClick={() => setRemoving(grant)}>
                                            {t('STAFF.FORM_ACCESS.REMOVE')}
                                        </Button>
                                    )}
                                </div>
                            </li>
                        );
                    })}
                </ul>
            )}

            {canManage &&
                (!isAdmin ? (
                    <p role="note" className="text-sm text-black-700">
                        {t('STAFF.FORM_ACCESS.NO_PICKER')}
                    </p>
                ) : roles.length === 0 ? (
                    <p role="note" className="text-sm text-black-700">
                        {t('STAFF.FORM_ACCESS.NO_ROLE_TO_GIVE')}
                    </p>
                ) : (
                    <form onSubmit={add} noValidate aria-labelledby={`${id}-add`} className="flex flex-col gap-3 rounded border border-black-300 bg-black-100 p-4">
                        <h4 id={`${id}-add`} className="text-sm font-semibold text-black-900">
                            {t('STAFF.FORM_ACCESS.ADD')}
                        </h4>
                        <div className="flex flex-col gap-3 md:flex-row md:items-end">
                            <div className="flex min-w-0 flex-1 flex-col gap-1">
                                <label htmlFor={`${id}-subject`} className="text-sm font-medium text-black-700">
                                    {t('STAFF.FORM_ACCESS.SUBJECT_LABEL')}
                                </label>
                                <select id={`${id}-subject`} className={selectClass} value={subjectKey} onChange={(event) => setSubjectKey(event.target.value)} disabled={busy}>
                                    <option value="">{t('STAFF.FORM_ACCESS.SUBJECT_PLACEHOLDER')}</option>
                                    {subjects.some((item) => item.type === 'user') && (
                                        <optgroup label={t('STAFF.FORM_ACCESS.GROUP_PEOPLE')}>
                                            {subjects
                                                .filter((item) => item.type === 'user')
                                                .map((item) => (
                                                    <option key={item.key} value={item.key}>
                                                        {item.label}
                                                    </option>
                                                ))}
                                        </optgroup>
                                    )}
                                    {subjects.some((item) => item.type === 'group') && (
                                        <optgroup label={t('STAFF.FORM_ACCESS.GROUP_TEAMS')}>
                                            {subjects
                                                .filter((item) => item.type === 'group')
                                                .map((item) => (
                                                    <option key={item.key} value={item.key}>
                                                        {item.label}
                                                    </option>
                                                ))}
                                        </optgroup>
                                    )}
                                </select>
                            </div>
                            <div className="flex flex-col gap-1 md:w-44">
                                <label htmlFor={`${id}-role`} className="text-sm font-medium text-black-700">
                                    {t('STAFF.FORM_ACCESS.ROLE_LABEL')}
                                </label>
                                <select id={`${id}-role`} className={selectClass} value={chosenRole} onChange={(event) => setRole(event.target.value as GrantRole)} disabled={busy}>
                                    {roles.map((item) => (
                                        <option key={item} value={item}>
                                            {t(roleLocale(item).name)}
                                        </option>
                                    ))}
                                </select>
                            </div>
                            <Button type="submit" variant="primary" className="min-h-11 shrink-0 md:min-h-10" disabled={busy || !subject || !chosenRole}>
                                {t('STAFF.FORM_ACCESS.ADD_BUTTON')}
                            </Button>
                        </div>
                        {chosenRole && exportFlagApplies(chosenRole) && (
                            <label className="flex min-h-11 items-center gap-2 text-sm text-black-800 md:min-h-8">
                                <input type="checkbox" className="h-5 w-5 shrink-0" checked={allowExport} onChange={(event) => setAllowExport(event.target.checked)} disabled={busy} />
                                {t('STAFF.FORM_ACCESS.EXPORT')}
                            </label>
                        )}
                        <p className="text-xs text-black-600">{t('STAFF.FORM_ACCESS.EXPORT_NOTE')}</p>
                    </form>
                ))}

            <AlertDialog open={!!removing} onOpenChange={(open) => !open && setRemoving(null)}>
                <AlertDialogContent>
                    <AlertDialogHeader>
                        <AlertDialogTitle>{t('STAFF.FORM_ACCESS.REMOVE_TITLE', { name: removing ? nameOf(removing) : '' })}</AlertDialogTitle>
                        <AlertDialogDescription>{t('STAFF.FORM_ACCESS.REMOVE_BODY', { name: removing ? nameOf(removing) : '' })}</AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                        <AlertDialogCancel>{t('STAFF.FORM_ACCESS.CANCEL')}</AlertDialogCancel>
                        <AlertDialogAction
                            onClick={(event) => {
                                event.preventDefault();
                                confirmRemove();
                            }}
                        >
                            {t('STAFF.FORM_ACCESS.REMOVE')}
                        </AlertDialogAction>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>
        </div>
    );
}

function formatDay(value: string, language: string): string {
    // the server sends UTC without a zone mark
    const date = new Date(/(Z|[+-]\d\d:?\d\d)$/.test(value) ? value : `${value}Z`);
    if (Number.isNaN(date.getTime())) return '';
    return new Intl.DateTimeFormat(language, { dateStyle: 'medium' }).format(date);
}
