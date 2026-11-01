'use client';

import { useState } from 'react';

import { Plus } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import { useWorkspacePermissions } from '@app/lib/hooks/use-workspace-permissions';
import { WorkspacePermission } from '@app/models/enums/workspace-permission';
import { Button } from '@app/shadcn/components/ui/button';
import { AppInput } from '@app/shadcn/components/ui/input';
import { useAppSelector } from '@app/store/hooks';
import { useCreateOptionListMutation, useGetOptionListsQuery } from '@app/store/option-lists/api';
import { selectWorkspace } from '@app/store/workspaces/slice';

import OptionListEditor from './option-list-editor';

/** The server's refusal, in a sentence the page can show (its `message`), else the fallback. */
export const refusalText = (error: any, fallback: string): string => (typeof error?.data?.message === 'string' ? error.data.message : fallback);

export default function OptionListsClient() {
    const { t } = useTranslation('builder');
    const workspace = useAppSelector(selectWorkspace);
    const { can } = useWorkspacePermissions();
    const canEdit = can(WorkspacePermission.FORM_EDIT);
    const workspaceId = workspace?.id as string;
    const { data: lists, isLoading } = useGetOptionListsQuery({ workspaceId }, { skip: !workspaceId });
    const [createList, { isLoading: creating }] = useCreateOptionListMutation();
    const [name, setName] = useState('');
    const [opened, setOpened] = useState<string | null>(null);
    const [error, setError] = useState('');

    const create = async () => {
        setError('');
        const result: any = await createList({ workspaceId, name });
        if (result.data) {
            setName('');
            setOpened(result.data.id);
        } else setError(refusalText(result.error, t('LISTS.CREATE_FAILED')));
    };

    if (opened) return <OptionListEditor listId={opened} canEdit={canEdit} onClose={() => setOpened(null)} />;

    return (
        <div className="flex w-full max-w-[860px] flex-col gap-6 pb-10">
            <p className="max-w-[62ch] text-sm leading-relaxed text-black-600">{t('LISTS.INTRO')}</p>

            {canEdit && (
                <form
                    className="flex flex-col gap-2 sm:flex-row sm:items-end"
                    onSubmit={(event) => {
                        event.preventDefault();
                        if (name.trim()) void create();
                    }}
                >
                    <label className="flex flex-1 flex-col gap-1 text-sm text-black-800">
                        {t('LISTS.NEW_NAME')}
                        <AppInput className="w-full" value={name} maxLength={100} onChange={(event: any) => setName(event.target.value)} placeholder={t('LISTS.NEW_PLACEHOLDER')} />
                    </label>
                    <Button type="submit" disabled={!name.trim() || creating} className="min-h-11">
                        <Plus className="mr-1 h-4 w-4" aria-hidden="true" />
                        {t('LISTS.CREATE')}
                    </Button>
                </form>
            )}
            {error && (
                <p role="alert" className="text-sm text-red-700">
                    {error}
                </p>
            )}

            {isLoading ? (
                <p className="text-sm text-black-600">{t('LISTS.LOADING')}</p>
            ) : !lists?.length ? (
                <p className="rounded-lg border border-dashed border-black-400 p-6 text-sm text-black-700">{t('LISTS.EMPTY')}</p>
            ) : (
                <table className="w-full text-left text-sm">
                    <caption className="sr-only">{t('LISTS.TITLE')}</caption>
                    <thead className="text-xs text-black-600">
                        <tr>
                            <th scope="col" className="py-2 pr-3 font-medium">
                                {t('LISTS.COLUMN_NAME')}
                            </th>
                            <th scope="col" className="py-2 pr-3 font-medium">
                                {t('LISTS.COLUMN_ITEMS')}
                            </th>
                            <th scope="col" className="hidden py-2 pr-3 font-medium sm:table-cell">
                                {t('LISTS.COLUMN_FORMS')}
                            </th>
                            <th scope="col" className="py-2 font-medium">
                                <span className="sr-only">{t('LISTS.COLUMN_ACTIONS')}</span>
                            </th>
                        </tr>
                    </thead>
                    <tbody>
                        {lists.map((list) => (
                            <tr key={list.id} className="border-t border-black-300">
                                <th scope="row" className="py-3 pr-3 font-medium text-black-900">
                                    {list.name}
                                </th>
                                <td className="py-3 pr-3">{list.itemCount}</td>
                                <td className="hidden py-3 pr-3 sm:table-cell">{list.formsUsing}</td>
                                <td className="py-3 text-right">
                                    <button type="button" onClick={() => setOpened(list.id)} className="min-h-11 rounded-md px-3 text-sm font-medium underline" aria-label={t(canEdit ? 'LISTS.EDIT_NAMED' : 'LISTS.OPEN_NAMED', { name: list.name })}>
                                        {t(canEdit ? 'LISTS.EDIT' : 'LISTS.OPEN')}
                                    </button>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            )}
        </div>
    );
}
