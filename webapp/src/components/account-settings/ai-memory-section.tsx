'use client';

import { useState } from 'react';

import { Trans, useTranslation } from 'react-i18next';

import { Plus, X } from 'lucide-react';

import { useIntlLocale } from '@app/lib/hooks/use-intl-locale';

import { Button } from '@app/shadcn/components/ui/button';
import { useToast } from '@app/shadcn/components/ui/use-toast';
import { useAppSelector } from '@app/store/hooks';
import { useAddAIMemoryEntryMutation, useDeleteAIMemoryEntryMutation, useGetAIMemoryQuery } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';

interface MemoryEntry {
    id: string;
    text: string;
    at?: string;
    source?: string;
}

/**
 * The creator's AI preference memory — a living document (plan §2.4).
 * Transparency is the contract: every line the AI remembers is visible here,
 * deletable, and the user can add their own. Nothing hidden, no embeddings.
 */
export default function AIMemorySection() {
    const { t } = useTranslation();
    const locale = useIntlLocale();
    const workspace = useAppSelector(selectWorkspace);
    const { toast } = useToast();
    const { data: entries = [], isLoading } = useGetAIMemoryQuery(workspace?.id, { skip: !workspace?.id });
    const [addEntry, { isLoading: isAdding }] = useAddAIMemoryEntryMutation();
    const [deleteEntry] = useDeleteAIMemoryEntryMutation();
    const [draft, setDraft] = useState('');

    const handleAdd = async () => {
        const text = draft.trim();
        if (!text) return;
        const response: any = await addEntry({ workspace_id: workspace.id, body: { text } });
        if (response.data) {
            setDraft('');
        } else {
            toast({ description: t('STAFF.AI_MEMORY.SAVE_FAILED'), variant: 'destructive' });
        }
    };

    return (
        <div className="border-black-300 flex max-w-[640px] flex-col gap-4 rounded border bg-white p-6">
            <div className="flex flex-col gap-1">
                <h2 className="text-black-900 text-sm font-semibold">{t('STAFF.AI_MEMORY.TITLE')}</h2>
                <p className="text-black-600 text-xs leading-relaxed">
                    <Trans i18nKey="STAFF.AI_MEMORY.INTRO" values={{ workspace: workspace?.title || t('STAFF.AI_MEMORY.THIS_WORKSPACE') }} components={{ 1: <span className="font-medium" /> }} />
                </p>
            </div>

            {isLoading ? (
                <p className="text-black-600 text-xs">{t('STAFF.SESSIONS.LOADING')}</p>
            ) : entries.length === 0 ? (
                <p className="text-black-600 border-black-400 rounded-md border border-dashed px-3 py-4 text-center text-xs">{t('STAFF.AI_MEMORY.EMPTY')}</p>
            ) : (
                <ul className="flex flex-col gap-1.5">
                    {(entries as MemoryEntry[]).map((entry) => (
                        <li key={entry.id} className="group border-black-300 flex items-start justify-between gap-3 rounded-md border px-3 py-2">
                            <div className="min-w-0">
                                <p className="text-black-800 text-[13px] leading-relaxed">{entry.text}</p>
                                <p className="text-black-600 text-[10.5px]">
                                    {entry.source === 'manual' ? t('STAFF.AI_MEMORY.ADDED_BY_YOU') : t('STAFF.AI_MEMORY.LEARNED')}
                                    {entry.at ? ` · ${new Date(entry.at).toLocaleDateString(locale)}` : ''}
                                </p>
                            </div>
                            <button
                                type="button"
                                aria-label={t('STAFF.AI_MEMORY.FORGET', { text: entry.text })}
                                onClick={() => deleteEntry({ workspace_id: workspace.id, entry_id: entry.id })}
                                className="text-black-600 mt-0.5 shrink-0 rounded p-1 transition-colors hover:bg-[#FBEFEF] hover:text-[#C43D3D]"
                            >
                                <X className="h-3.5 w-3.5" />
                            </button>
                        </li>
                    ))}
                </ul>
            )}

            <div className="flex items-center gap-2">
                <input
                    value={draft}
                    maxLength={300}
                    placeholder={t('STAFF.AI_MEMORY.PLACEHOLDER')}
                    onChange={(e) => setDraft(e.target.value)}
                    onKeyDown={(e) => {
                        if (e.key === 'Enter') handleAdd();
                    }}
                    className="border-control text-black-900 placeholder:text-black-600 focus:border-brand-500 h-9 w-full rounded-md border bg-white px-3 text-[13px] outline-hidden transition duration-150"
                />
                <Button size="sm" variant="v2Button" isLoading={isAdding} disabled={!draft.trim()} onClick={handleAdd} icon={<Plus className="h-4 w-4" />}>
                    {t('STAFF.AI_MEMORY.ADD')}
                </Button>
            </div>
        </div>
    );
}
