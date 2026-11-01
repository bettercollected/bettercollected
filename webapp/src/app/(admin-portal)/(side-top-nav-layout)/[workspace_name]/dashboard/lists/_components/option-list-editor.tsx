'use client';

import { ChangeEvent, useEffect, useRef, useState } from 'react';

import { ArrowLeft, Download, Plus, Trash2, Upload } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import { Button } from '@app/shadcn/components/ui/button';
import { AppInput } from '@app/shadcn/components/ui/input';
import { useToast } from '@app/shadcn/components/ui/use-toast';
import { useAppSelector } from '@app/store/hooks';
import { OptionListItem, useDeleteOptionListMutation, useExportOptionListCsvMutation, useGetOptionListQuery, useImportOptionListCsvMutation, useUpdateOptionListMutation } from '@app/store/option-lists/api';
import { selectWorkspace } from '@app/store/workspaces/slice';

import { refusalText } from './option-lists-client';

interface Props {
    listId: string;
    canEdit: boolean;
    onClose: () => void;
}

/** One list: its name, order and items (a label and an optional group each), with a CSV import and export. */
export default function OptionListEditor({ listId, canEdit, onClose }: Props) {
    const { t } = useTranslation('builder');
    const { toast } = useToast();
    const workspace = useAppSelector(selectWorkspace);
    const workspaceId = workspace?.id as string;
    const { data: list, isLoading } = useGetOptionListQuery({ workspaceId, listId }, { skip: !workspaceId });
    const [update, { isLoading: saving }] = useUpdateOptionListMutation();
    const [remove] = useDeleteOptionListMutation();
    const [importCsv] = useImportOptionListCsvMutation();
    const [exportCsv] = useExportOptionListCsvMutation();
    const fileRef = useRef<HTMLInputElement>(null);
    const [name, setName] = useState('');
    const [order, setOrder] = useState<'manual' | 'alphabetical'>('manual');
    const [items, setItems] = useState<OptionListItem[]>([]);
    const [revision, setRevision] = useState<number | undefined>();
    const [error, setError] = useState('');
    const [dirty, setDirty] = useState(false);

    // a fresh copy replaces the draft only while nothing was edited (a save, an import)
    useEffect(() => {
        if (!list || dirty) return;
        setName(list.name);
        setOrder(list.order);
        setItems(list.items.map((item) => ({ id: item.id, label: item.label, group: item.group ?? '' })));
        setRevision(list.revision);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [list]);

    if (isLoading || !list) return <p className="pb-10 text-sm text-black-600">{t('LISTS.LOADING')}</p>;

    const touch =
        <T,>(setter: (value: T) => void) =>
        (value: T) => {
            setter(value);
            setDirty(true);
        };

    const save = async () => {
        setError('');
        const result: any = await update({ workspaceId, listId, name, order, items: items.map((item) => ({ id: item.id, label: item.label, group: item.group || null })), expectedRevision: revision });
        if (result.data) {
            setDirty(false);
            toast({ description: t('LISTS.SAVED') });
        } else if (result.error?.status === 409 && result.error?.data?.code === 'list_changed') setError(t('LISTS.CHANGED_ELSEWHERE'));
        else setError(refusalText(result.error, t('LISTS.SAVE_FAILED')));
    };

    const onFile = async (event: ChangeEvent<HTMLInputElement>) => {
        const file = event.target.files?.[0];
        event.target.value = '';
        if (!file) return;
        // an import replaces the items: edits that are not saved would be lost
        if (dirty && !window.confirm(t('LISTS.CONFIRM_IMPORT'))) return;
        setError('');
        const result: any = await importCsv({ workspaceId, listId, csv: await file.text(), expectedRevision: revision });
        if (result.data) {
            setDirty(false);
            toast({ description: t('LISTS.IMPORTED', { count: result.data.totalItems }) });
        } else setError(refusalText(result.error, t('LISTS.IMPORT_FAILED')));
    };

    const download = async () => {
        const result: any = await exportCsv({ workspaceId, listId });
        if (typeof result.data !== 'string') return setError(t('LISTS.EXPORT_FAILED'));
        const url = URL.createObjectURL(new Blob([result.data], { type: 'text/csv;charset=utf-8' }));
        const link = document.createElement('a');
        link.href = url;
        link.download = `${name || 'list'}.csv`;
        link.click();
        URL.revokeObjectURL(url);
    };

    const erase = async () => {
        if (!window.confirm(t('LISTS.CONFIRM_DELETE', { name: list.name }))) return;
        const result: any = await remove({ workspaceId, listId });
        if (result.error)
            setError(result.error?.data?.code === 'list_in_use' ? t('LISTS.IN_USE', { forms: (result.error.data.forms ?? []).map((form: any) => form.title || t('LISTS.UNTITLED_FORM')).join(', ') }) : refusalText(result.error, t('LISTS.DELETE_FAILED')));
        else onClose();
    };

    const setItem = (index: number, patch: Partial<OptionListItem>) => touch(setItems)(items.map((item, position) => (position === index ? { ...item, ...patch } : item)));

    return (
        <div className="flex w-full max-w-[860px] flex-col gap-5 pb-10">
            <button
                type="button"
                onClick={() => {
                    if (dirty && !window.confirm(t('LISTS.CONFIRM_LEAVE'))) return;
                    onClose();
                }}
                className="flex min-h-11 w-fit items-center gap-1 text-sm font-medium underline"
            >
                <ArrowLeft className="h-4 w-4" aria-hidden="true" />
                {t('LISTS.BACK')}
            </button>

            <div className="flex flex-col gap-3 sm:flex-row">
                <label className="flex flex-1 flex-col gap-1 text-sm text-black-800">
                    {t('LISTS.NEW_NAME')}
                    <AppInput className="w-full" value={name} maxLength={100} disabled={!canEdit} onChange={(event: any) => touch(setName)(event.target.value)} />
                </label>
                <label className="flex flex-col gap-1 text-sm text-black-800">
                    {t('LISTS.ORDER')}
                    <select value={order} disabled={!canEdit} onChange={(event) => touch(setOrder)(event.target.value as 'manual' | 'alphabetical')} className="min-h-11 rounded-md border border-control bg-white px-2 text-sm">
                        <option value="manual">{t('LISTS.ORDER_MANUAL')}</option>
                        <option value="alphabetical">{t('LISTS.ORDER_ALPHABETICAL')}</option>
                    </select>
                </label>
            </div>

            <p className="text-xs leading-relaxed text-black-600">{t('LISTS.GROUP_NOTE')}</p>
            {list.usedBy.length > 0 && <p className="text-xs text-black-700">{t('LISTS.USED_BY', { forms: list.usedBy.map((form) => form.title || t('LISTS.UNTITLED_FORM')).join(', ') })}</p>}

            <div className="flex flex-wrap items-center gap-2">
                <Button type="button" variant="secondary" onClick={download} className="min-h-11">
                    <Download className="mr-1 h-4 w-4" aria-hidden="true" />
                    {t('LISTS.EXPORT')}
                </Button>
                {canEdit && (
                    <>
                        <input ref={fileRef} type="file" accept=".csv,text/csv" className="sr-only" aria-label={t('LISTS.IMPORT')} onChange={onFile} data-testid="list-import" />
                        <Button type="button" variant="secondary" onClick={() => fileRef.current?.click()} className="min-h-11">
                            <Upload className="mr-1 h-4 w-4" aria-hidden="true" />
                            {t('LISTS.IMPORT')}
                        </Button>
                    </>
                )}
            </div>
            {canEdit && <p className="text-xs text-black-600">{t('LISTS.IMPORT_NOTE')}</p>}

            <table className="w-full table-fixed text-left text-sm">
                <caption className="sr-only">{t('LISTS.ITEMS')}</caption>
                <thead className="text-xs text-black-600">
                    <tr>
                        <th scope="col" className="py-2 pr-2 font-medium">
                            {t('LISTS.COLUMN_LABEL')}
                        </th>
                        <th scope="col" className="py-2 pr-2 font-medium">
                            {t('LISTS.COLUMN_GROUP')}
                        </th>
                        {canEdit && (
                            <th scope="col" className="w-11 py-2 font-medium">
                                <span className="sr-only">{t('LISTS.COLUMN_ACTIONS')}</span>
                            </th>
                        )}
                    </tr>
                </thead>
                <tbody>
                    {items.map((item, index) => (
                        <tr key={item.id ?? `new-${index}`} className="border-t border-black-300">
                            <td className="py-1.5 pr-2">
                                <AppInput className="w-full min-w-0" value={item.label} maxLength={200} disabled={!canEdit} aria-label={t('LISTS.LABEL_OF', { n: index + 1 })} onChange={(event: any) => setItem(index, { label: event.target.value })} />
                            </td>
                            <td className="py-1.5 pr-2">
                                <AppInput className="w-full min-w-0" value={item.group ?? ''} maxLength={200} disabled={!canEdit} aria-label={t('LISTS.GROUP_OF', { n: index + 1 })} onChange={(event: any) => setItem(index, { group: event.target.value })} />
                            </td>
                            {canEdit && (
                                <td className="py-1.5">
                                    <button
                                        type="button"
                                        aria-label={t('LISTS.REMOVE_ITEM', { n: index + 1 })}
                                        onClick={() => touch(setItems)(items.filter((_item, position) => position !== index))}
                                        className="flex h-11 w-11 items-center justify-center rounded-md"
                                    >
                                        <Trash2 className="h-4 w-4" aria-hidden="true" />
                                    </button>
                                </td>
                            )}
                        </tr>
                    ))}
                </tbody>
            </table>
            {canEdit && (
                <Button type="button" variant="secondary" onClick={() => touch(setItems)([...items, { label: '', group: '' }])} className="min-h-11 w-fit" disabled={items.length >= 2000}>
                    <Plus className="mr-1 h-4 w-4" aria-hidden="true" />
                    {t('LISTS.ADD_ITEM')}
                </Button>
            )}

            {error && (
                <p role="alert" className="text-sm text-red-700">
                    {error}
                </p>
            )}
            {canEdit && (
                <div className="flex flex-wrap items-center gap-3 border-t border-black-300 pt-4">
                    <Button type="button" onClick={save} disabled={!dirty || saving} className="min-h-11">
                        {t('LISTS.SAVE')}
                    </Button>
                    <button type="button" onClick={erase} className="min-h-11 text-sm font-medium text-red-700 underline">
                        {t('LISTS.DELETE')}
                    </button>
                </div>
            )}
        </div>
    );
}
