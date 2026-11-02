'use client';

import { FormEvent, useMemo, useState } from 'react';

import { ChevronDown, ChevronRight, Pencil, Trash2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import { useWorkspacePermissions } from '@app/lib/hooks/use-workspace-permissions';
import { WorkspacePermission } from '@app/models/enums/workspace-permission';
import { Button } from '@app/shadcn/components/ui/button';
import { AppInput } from '@app/shadcn/components/ui/input';
import { useToast } from '@app/shadcn/components/ui/use-toast';
import { useAppSelector } from '@app/store/hooks';
import { SectionSummary, useDeleteSectionMutation, useGetSectionQuery, useGetSectionsQuery, useUpdateSectionDetailsMutation } from '@app/store/reusable-sections/api';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { plainTitle, refusalText } from '@app/utils/reusable-sections';

/** The questions of one section, read-only: what inserting it would add. */
export function SectionPreview({ workspaceId, sectionId }: { workspaceId: string; sectionId: string }) {
    const { t } = useTranslation('builder');
    const { data, isLoading } = useGetSectionQuery({ workspaceId, sectionId });
    if (isLoading || !data) return <p className="text-sm text-black-600">{t('SECTIONS_LIB.PAGE.LOADING')}</p>;
    return (
        <div className="flex flex-col gap-2">
            <ol className="flex list-decimal flex-col gap-1 pl-5 text-sm text-black-800">
                {data.fields.map((field) => (
                    <li key={field.id}>
                        <span>{plainTitle(field) || t('SECTIONS_LIB.UNTITLED')}</span> <span className="text-xs text-black-600">({t(`FIELD_TYPES.${field.type}.NAME`, { defaultValue: String(field.type) })})</span>
                    </li>
                ))}
            </ol>
            {data.containers.length > 0 && <p className="text-xs text-black-600">{t('SECTIONS_LIB.PAGE.CONTAINERS', { count: data.containers.length })}</p>}
        </div>
    );
}

function Row({ section, workspaceId, canEdit, open, onToggle }: { section: SectionSummary; workspaceId: string; canEdit: boolean; open: boolean; onToggle: () => void }) {
    const { t } = useTranslation('builder');
    const { toast } = useToast();
    const [rename] = useUpdateSectionDetailsMutation();
    const [remove] = useDeleteSectionMutation();
    const [editing, setEditing] = useState(false);
    const [name, setName] = useState(section.name);
    const [error, setError] = useState('');

    const save = async (event: FormEvent) => {
        event.preventDefault();
        if (!name.trim()) return;
        const result: any = await rename({ workspaceId, sectionId: section.id, name: name.trim() });
        if (result.data) {
            setEditing(false);
            setError('');
        } else setError(result.error?.data?.code === 'name_taken' ? t('SECTIONS_LIB.PAGE.NAME_TAKEN') : refusalText(result.error, t('SECTIONS_LIB.PAGE.RENAME_FAILED')));
    };
    const erase = async () => {
        if (!window.confirm(t('SECTIONS_LIB.PAGE.CONFIRM_DELETE', { name: section.name }))) return;
        const result: any = await remove({ workspaceId, sectionId: section.id });
        if (result.error) toast({ variant: 'destructive', description: refusalText(result.error, t('SECTIONS_LIB.PAGE.DELETE_FAILED')) });
        else toast({ description: t('SECTIONS_LIB.PAGE.DELETED', { name: section.name }) });
    };

    return (
        <li className="flex flex-col gap-2 border-t border-black-300 py-3 first:border-t-0">
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
                {/* the name gets the whole line on a phone, and is never cut */}
                <button type="button" onClick={onToggle} aria-expanded={open} className="flex min-h-11 w-full min-w-0 items-center gap-2 text-left sm:w-auto sm:flex-1" aria-label={t('SECTIONS_LIB.PAGE.PREVIEW_NAMED', { name: section.name })}>
                    {open ? <ChevronDown className="h-4 w-4 shrink-0" aria-hidden="true" /> : <ChevronRight className="h-4 w-4 shrink-0" aria-hidden="true" />}
                    <span className="min-w-0">
                        <span className="block text-sm font-medium break-words text-black-900">{section.name}</span>
                        {section.description && <span className="block text-xs break-words text-black-600">{section.description}</span>}
                    </span>
                </button>
                <span className="pl-6 text-xs text-black-700 sm:pl-0">{t('SECTIONS_LIB.PAGE.QUESTIONS', { count: section.questionCount })}</span>
                <span className="text-xs text-black-700">{t('SECTIONS_LIB.PAGE.VERSION', { version: section.version })}</span>
                {canEdit && (
                    <span className="ml-auto flex gap-1 sm:ml-0">
                        <button
                            type="button"
                            onClick={() => setEditing((value) => !value)}
                            className="flex min-h-11 min-w-11 items-center justify-center rounded-md hover:bg-black-100"
                            aria-label={t('SECTIONS_LIB.PAGE.RENAME_NAMED', { name: section.name })}
                        >
                            <Pencil className="h-4 w-4" aria-hidden="true" />
                        </button>
                        <button type="button" onClick={erase} className="flex min-h-11 min-w-11 items-center justify-center rounded-md text-red-700 hover:bg-red-50" aria-label={t('SECTIONS_LIB.PAGE.DELETE_NAMED', { name: section.name })}>
                            <Trash2 className="h-4 w-4" aria-hidden="true" />
                        </button>
                    </span>
                )}
            </div>
            {editing && (
                <form className="flex flex-col gap-2 sm:flex-row sm:items-end" onSubmit={save}>
                    <label className="flex flex-1 flex-col gap-1 text-sm text-black-800">
                        {t('SECTIONS_LIB.SAVE.NAME')}
                        <AppInput className="w-full" value={name} maxLength={100} onChange={(event: any) => setName(event.target.value)} />
                    </label>
                    <Button type="submit" className="min-h-11" disabled={!name.trim()}>
                        {t('SECTIONS_LIB.PAGE.RENAME')}
                    </Button>
                </form>
            )}
            {error && (
                <p role="alert" className="text-sm text-red-700">
                    {error}
                </p>
            )}
            {open && (
                <div className="rounded-lg bg-black-100 p-4">
                    <SectionPreview workspaceId={workspaceId} sectionId={section.id} />
                </div>
            )}
        </li>
    );
}

/** The library page: the workspace's reusable sections, searchable, with preview, rename and delete. */
export default function SectionsClient() {
    const { t } = useTranslation('builder');
    const workspace = useAppSelector(selectWorkspace);
    const { can } = useWorkspacePermissions();
    const canEdit = can(WorkspacePermission.FORM_EDIT);
    const workspaceId = workspace?.id as string;
    const { data: sections, isLoading } = useGetSectionsQuery({ workspaceId }, { skip: !workspaceId });
    const [query, setQuery] = useState('');
    const [open, setOpen] = useState<string | null>(null);
    const shown = useMemo(() => {
        const q = query.trim().toLowerCase();
        return (sections ?? []).filter((section) => !q || section.name.toLowerCase().includes(q) || (section.description ?? '').toLowerCase().includes(q));
    }, [sections, query]);

    return (
        <div className="flex w-full max-w-[860px] flex-col gap-6 pb-10">
            <p className="max-w-[62ch] text-sm leading-relaxed text-black-600">{t('SECTIONS_LIB.PAGE.INTRO')}</p>
            {isLoading ? (
                <p className="text-sm text-black-600">{t('SECTIONS_LIB.PAGE.LOADING')}</p>
            ) : !sections?.length ? (
                <p className="rounded-lg border border-dashed border-black-400 p-6 text-sm text-black-700">{t('SECTIONS_LIB.PAGE.EMPTY')}</p>
            ) : (
                <>
                    <label className="flex max-w-sm flex-col gap-1 text-sm text-black-800">
                        {t('SECTIONS_LIB.PAGE.SEARCH')}
                        <AppInput className="w-full" value={query} onChange={(event: any) => setQuery(event.target.value)} />
                    </label>
                    {shown.length === 0 ? (
                        <p className="text-sm text-black-700">{t('SECTIONS_LIB.PAGE.NO_MATCH', { query })}</p>
                    ) : (
                        <ul aria-label={t('SECTIONS_LIB.PAGE.TITLE')}>
                            {shown.map((section) => (
                                <Row key={section.id} section={section} workspaceId={workspaceId} canEdit={canEdit} open={open === section.id} onToggle={() => setOpen(open === section.id ? null : section.id)} />
                            ))}
                        </ul>
                    )}
                </>
            )}
        </div>
    );
}
