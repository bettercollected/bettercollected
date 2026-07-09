'use client';

import { useState } from 'react';

import { Plus, X } from 'lucide-react';

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
            toast({ description: 'Could not save that. Please try again.', variant: 'destructive' });
        }
    };

    return (
        <div className="border-black-200 flex max-w-[640px] flex-col gap-4 rounded-lg border bg-white p-6">
            <div className="flex flex-col gap-1">
                <h2 className="text-black-900 text-sm font-semibold">What the AI remembers about your style</h2>
                <p className="text-black-600 text-xs leading-relaxed">
                    Preferences the assistant has picked up from working with you in <span className="font-medium">{workspace?.title || 'this workspace'}</span> — plus any you add yourself. It reads these when building forms; your request and your organization&apos;s rules
                    always take priority. Delete anything, anytime.
                </p>
            </div>

            {isLoading ? (
                <p className="text-black-500 text-xs">Loading…</p>
            ) : entries.length === 0 ? (
                <p className="text-black-500 border-black-200 rounded-md border border-dashed px-3 py-4 text-center text-xs">Nothing remembered yet — it fills in as you build forms with the assistant.</p>
            ) : (
                <ul className="flex flex-col gap-1.5">
                    {(entries as MemoryEntry[]).map((entry) => (
                        <li key={entry.id} className="group border-black-200 flex items-start justify-between gap-3 rounded-md border px-3 py-2">
                            <div className="min-w-0">
                                <p className="text-black-800 text-[13px] leading-relaxed">{entry.text}</p>
                                <p className="text-black-400 text-[10.5px]">
                                    {entry.source === 'manual' ? 'Added by you' : 'Learned from a session'}
                                    {entry.at ? ` · ${new Date(entry.at).toLocaleDateString()}` : ''}
                                </p>
                            </div>
                            <button
                                type="button"
                                aria-label={`Forget "${entry.text}"`}
                                onClick={() => deleteEntry({ workspace_id: workspace.id, entry_id: entry.id })}
                                className="text-black-400 mt-0.5 shrink-0 rounded p-1 transition-colors hover:bg-[#FBEFEF] hover:text-[#C43D3D]"
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
                    placeholder="Add a preference, e.g. “Keep pages under 5 questions”"
                    onChange={(e) => setDraft(e.target.value)}
                    onKeyDown={(e) => {
                        if (e.key === 'Enter') handleAdd();
                    }}
                    className="border-black-300 text-black-900 placeholder:text-black-400 focus:border-brand-500 h-9 w-full rounded-md border bg-white px-3 text-[13px] outline-none transition duration-150 focus:shadow-[0_0_0_3px_rgba(36,86,204,0.15)]"
                />
                <Button size="sm" variant="v2Button" isLoading={isAdding} disabled={!draft.trim()} onClick={handleAdd} icon={<Plus className="h-4 w-4" />}>
                    Add
                </Button>
            </div>
        </div>
    );
}
