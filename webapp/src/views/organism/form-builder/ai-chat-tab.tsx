'use client';

import { useEffect, useRef, useState } from 'react';

import { BookOpen, Check, Plus, Send, ShieldCheck, X } from 'lucide-react';

import { StandardFormDto } from '@app/models/dtos/form';
import { deepCopy } from '@app/utils/object-utils';
import { selectForm, setForm } from '@app/store/forms/slice';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import useFormFieldsAtom from '@app/store/jotai/field-selectors';
import { useFormState } from '@app/store/jotai/form';
import { useApplyAIReviewFixMutation, useChatEditFormWithAIMutation, useReviewFormWithAIMutation } from '@app/store/redux/form-api';
import { useAddAIMemoryEntryMutation, useDeleteAIMemoryEntryMutation, useGetAIMemoryQuery } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';

interface TurnResult {
    ok: boolean;
    message: string;
}

interface ReviewFinding {
    severity: 'high' | 'medium' | 'info';
    message: string;
    fieldId?: string | null;
    fix?: { description: string; ops: any[] } | null;
    applied?: boolean;
    applying?: boolean;
    applyError?: string;
}

interface ChatTurn {
    role: 'user' | 'assistant' | 'memory' | 'review';
    content: string;
    results?: TurnResult[];
    error?: boolean;
    // role 'assistant' + error only — the failed message, so it can be retried.
    retryMessage?: string;
    // role 'memory' only — the learned entry, so it can be forgotten in place.
    entryId?: string;
    forgotten?: boolean;
    // role 'review' only.
    findings?: ReviewFinding[];
}

const MAX_MESSAGE_CHARS = 4000; // mirrors the backend's FormAIChatRequest limit
const MAX_PERSISTED_TURNS = 100;

const EXAMPLE_PROMPTS = ['Add a required work email question on page 1', 'Make everything on page 2 optional', 'Rename the form to Customer check-in'];

const SEVERITY_STYLES: Record<ReviewFinding['severity'], { label: string; chip: string }> = {
    high: { label: 'High', chip: 'bg-[#FBEFEF] text-[#C43D3D]' },
    medium: { label: 'Medium', chip: 'bg-[#FDF3E7] text-[#B25E09]' },
    info: { label: 'Info', chip: 'bg-black-100 text-black-600' }
};

interface MemoryEntry {
    id: string;
    text: string;
    at?: string;
    source?: string;
}

/**
 * The form-editing copilot (plan §2.2). One turn = typed ops applied to the
 * draft server-side; the canvas updates through setFormFields, which records
 * exactly one undo snapshot — so Ctrl+Z reverts a whole AI turn. The per-turn
 * change list comes straight from the backend's OpResults: what the AI
 * actually did, visibly, including what failed.
 *
 * Memory transparency (plan §2.4): the panel shows everything the assistant
 * remembers about the creator's style, editable in place — and when a turn
 * teaches it something new (extraction runs server-side after the reply), a
 * "Remembered" notice appears in the chat with an immediate Forget. The AI
 * never learns silently.
 */
export default function AIChatTab({ memoryPollDelaysMs = [4000, 10000] }: { memoryPollDelaysMs?: number[] }) {
    const dispatch = useAppDispatch();
    const workspace = useAppSelector(selectWorkspace);
    const standardForm: StandardFormDto = useAppSelector(selectForm);
    const { setFormFields } = useFormFieldsAtom();
    const { setFormState, formState } = useFormState();
    const [chatEdit, { isLoading }] = useChatEditFormWithAIMutation();
    const [reviewForm, { isLoading: isReviewing }] = useReviewFormWithAIMutation();
    const [applyReviewFix] = useApplyAIReviewFixMutation();

    const { data: memoryEntries = [], refetch: refetchMemory } = useGetAIMemoryQuery(workspace?.id, { skip: !workspace?.id });
    const [deleteMemoryEntry] = useDeleteAIMemoryEntryMutation();
    const [addMemoryEntry, { isLoading: isAddingMemory }] = useAddAIMemoryEntryMutation();

    const [turns, setTurns] = useState<ChatTurn[]>([]);
    const [sessionId, setSessionId] = useState<string | null>(null);
    const [input, setInput] = useState('');
    const [showMemory, setShowMemory] = useState(false);
    const [memoryDraft, setMemoryDraft] = useState('');
    const listRef = useRef<HTMLDivElement>(null);

    // The tab unmounts whenever the user switches to Page/Form/Design (Radix
    // Tabs), which used to destroy the whole conversation — persist it per
    // form so checking the canvas doesn't cost the chat.
    const storageKey = standardForm?.formId ? `bc:ai-chat-state:${standardForm.formId}` : null;
    const restoredKeyRef = useRef<string | null>(null);
    useEffect(() => {
        if (!storageKey || restoredKeyRef.current === storageKey) return;
        restoredKeyRef.current = storageKey;
        try {
            const saved = sessionStorage.getItem(storageKey);
            if (saved) {
                const parsed = JSON.parse(saved);
                if (Array.isArray(parsed.turns)) setTurns(parsed.turns);
                setSessionId(parsed.sessionId ?? null);
                scrollToEnd();
            }
        } catch {
            /* a corrupt stash only costs the restored history */
        }
    }, [storageKey]);
    useEffect(() => {
        if (!storageKey || restoredKeyRef.current !== storageKey) return;
        // Nothing worth saving also guards the pre-restore render from
        // clobbering an existing stash with the initial empty state.
        if (!turns.length && !sessionId) return;
        try {
            // Strip transient flags: a persisted `applying` would freeze a Fix
            // button forever after a remount.
            const persistable = turns.slice(-MAX_PERSISTED_TURNS).map((turn) => (turn.findings ? { ...turn, findings: turn.findings.map(({ applying, ...finding }) => finding) } : turn));
            sessionStorage.setItem(storageKey, JSON.stringify({ turns: persistable, sessionId }));
        } catch {
            /* quota — the conversation just won't survive a remount */
        }
    }, [turns, sessionId, storageKey]);

    // Latest entries + already-surfaced ids, for diffing after a turn without
    // stale-closure trouble.
    const entriesRef = useRef<MemoryEntry[]>([]);
    entriesRef.current = memoryEntries as MemoryEntry[];
    const noticedIdsRef = useRef<Set<string>>(new Set());

    // Extraction is a background task after the reply — poll briefly and
    // surface anything the assistant just learned from this turn.
    const surfaceNewMemories = (beforeIds: Set<string>) => {
        memoryPollDelaysMs.forEach((delay) => {
            setTimeout(async () => {
                const { data } = await refetchMemory();
                const fresh = ((data as MemoryEntry[]) ?? []).filter((entry) => entry.source !== 'manual' && !beforeIds.has(entry.id) && !noticedIdsRef.current.has(entry.id));
                if (!fresh.length) return;
                fresh.forEach((entry) => noticedIdsRef.current.add(entry.id));
                setTurns((t) => [...t, ...fresh.map((entry): ChatTurn => ({ role: 'memory', content: entry.text, entryId: entry.id }))]);
                scrollToEnd();
            }, delay);
        });
    };

    const forgetFromNotice = async (turnIndex: number, entryId: string) => {
        await deleteMemoryEntry({ workspace_id: workspace.id, entry_id: entryId });
        setTurns((t) => t.map((turn, i) => (i === turnIndex ? { ...turn, forgotten: true } : turn)));
    };

    const handleAddMemory = async () => {
        const text = memoryDraft.trim();
        if (!text) return;
        const response: any = await addMemoryEntry({ workspace_id: workspace.id, body: { text } });
        if (response.data) setMemoryDraft('');
    };

    // One canvas-apply path for chat turns and review fixes. deepCopy per
    // store is LOAD-BEARING — see the note in send().
    const applyFormToCanvas = (form: any) => {
        setFormFields(deepCopy(form.fields ?? []));
        setFormState({ ...formState, title: form.title ?? formState.title });
        dispatch(setForm({ ...standardForm, title: form.title, description: form.description, fields: deepCopy(form.fields ?? []) }));
    };

    // Compliance copilot (plan §2, P2): read-only review; each finding's fix
    // is applied individually and visibly — no bulk silent rewrite.
    const runReview = async () => {
        if (isReviewing) return;
        const response: any = await reviewForm({ workspaceId: workspace.id, formId: standardForm.formId });
        if (response.data) {
            setTurns((t) => [...t, { role: 'review', content: response.data.summary, findings: response.data.findings ?? [] }]);
        } else {
            const detail = typeof response.error?.data === 'string' ? response.error.data : 'The review failed — nothing was changed. Please try again.';
            setTurns((t) => [...t, { role: 'assistant', content: detail, error: true }]);
        }
        scrollToEnd();
    };

    const patchFinding = (turnIndex: number, findingIndex: number, patch: Partial<ReviewFinding>) => {
        setTurns((t) => t.map((turn, i) => (i === turnIndex && turn.findings ? { ...turn, findings: turn.findings.map((f, j) => (j === findingIndex ? { ...f, ...patch } : f)) } : turn)));
    };

    const applyFix = async (turnIndex: number, findingIndex: number) => {
        const finding = turns[turnIndex]?.findings?.[findingIndex];
        if (!finding?.fix || finding.applying) return;
        patchFinding(turnIndex, findingIndex, { applying: true, applyError: undefined });
        const response: any = await applyReviewFix({ workspaceId: workspace.id, formId: standardForm.formId, body: { ops: finding.fix.ops } });
        const applied = !!response.data?.results?.some((r: TurnResult) => r.ok);
        if (applied) {
            patchFinding(turnIndex, findingIndex, { applying: false, applied: true });
            applyFormToCanvas(response.data.form);
        } else {
            const failure = response.data?.results?.find((r: TurnResult) => !r.ok)?.message;
            patchFinding(turnIndex, findingIndex, { applying: false, applyError: failure ?? 'The fix could not be applied — please try again.' });
        }
    };

    const scrollToEnd = () => {
        requestAnimationFrame(() => listRef.current?.scrollTo?.({ top: listRef.current.scrollHeight, behavior: 'smooth' }));
    };

    // Start-with-AI handoff: the dashboard dialog stashes the creation prompt
    // and routes here — consume it exactly once and send it as the first turn
    // (removeItem BEFORE sending guards strict-mode double-mount).
    const consumedRef = useRef(false);
    useEffect(() => {
        if (!standardForm?.formId || consumedRef.current) return;
        const key = `bc:ai-prompt:${standardForm.formId}`;
        const pending = typeof window !== 'undefined' ? sessionStorage.getItem(key) : null;
        if (pending) {
            consumedRef.current = true;
            sessionStorage.removeItem(key);
            send(pending);
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [standardForm?.formId]);

    const send = async (messageOverride?: string) => {
        const message = (messageOverride ?? input).trim();
        if (!message || isLoading) return;
        setInput('');
        setTurns((t) => [...t, { role: 'user', content: message }]);
        scrollToEnd();
        const memoryIdsBeforeTurn = new Set(entriesRef.current.map((entry) => entry.id));

        const response: any = await chatEdit({
            workspaceId: workspace.id,
            formId: standardForm.formId,
            body: { message, sessionId }
        });

        if (response.data) {
            const { reply, results, form, sessionId: sid } = response.data;
            setSessionId(sid);
            // Apply the AI's edit to the canvas — ONE setFormFields call = one
            // undo snapshot, so a whole turn reverts with a single Ctrl+Z.
            //
            // deepCopy is LOAD-BEARING, twice over: Redux Toolkit freezes
            // whatever object graph is dispatched into it, and the builder's
            // field setters mutate fields in place — sharing references
            // between the response, Redux and jotai froze the canvas state
            // and every subsequent edit threw "Cannot assign to read only
            // property". Each store gets its own copy (mirrors how the edit
            // page hydrates with deepCopy at mount).
            if (results?.some((r: TurnResult) => r.ok)) {
                applyFormToCanvas(form);
            }
            setTurns((t) => [...t, { role: 'assistant', content: reply, results }]);
            surfaceNewMemories(memoryIdsBeforeTurn);
        } else {
            const detail = typeof response.error?.data === 'string' ? response.error.data : 'Something went wrong — nothing was changed. Please try again.';
            // Keep the failed message on the turn so one click retries it.
            setTurns((t) => [...t, { role: 'assistant', content: detail, error: true, retryMessage: message }]);
        }
        scrollToEnd();
    };

    return (
        <div className="flex h-full flex-col">
            <div className="px-4 pb-3">
                <div className="flex items-center justify-between gap-2">
                    <div className="text-black-600 text-xs font-semibold uppercase tracking-wide">Assistant</div>
                    <div className="flex items-center gap-1.5">
                        <button
                            type="button"
                            disabled={isReviewing}
                            onClick={runReview}
                            className="border-black-200 text-black-600 hover:bg-black-100 disabled:text-black-400 flex items-center gap-1.5 rounded-md border bg-white px-2 py-1 text-[11px] font-medium transition-colors"
                        >
                            <ShieldCheck className="h-3 w-3" />
                            {isReviewing ? 'Reviewing…' : 'Review'}
                        </button>
                        <button
                            type="button"
                            aria-expanded={showMemory}
                            onClick={() => setShowMemory((open) => !open)}
                            className={`flex items-center gap-1.5 rounded-md border px-2 py-1 text-[11px] font-medium transition-colors ${showMemory ? 'border-brand-200 bg-brand-100 text-brand-600' : 'border-black-200 text-black-600 hover:bg-black-100 bg-white'}`}
                        >
                            <BookOpen className="h-3 w-3" />
                            Memory{memoryEntries.length > 0 ? ` (${memoryEntries.length})` : ''}
                        </button>
                    </div>
                </div>
                <p className="text-black-600 mt-1 text-xs leading-relaxed">Describe a change — it lands on the canvas, and every change is listed. Undo reverts a whole turn.</p>
            </div>

            {showMemory && (
                <div className="border-black-200 mx-3 mb-3 flex max-h-56 flex-col gap-2 overflow-y-auto rounded-lg border bg-white p-3">
                    <p className="text-black-600 text-[11px] leading-relaxed">
                        Everything the assistant remembers about your style — used at the lowest priority, below your request and your organization&apos;s rules. Nothing here is hidden; forget any line, anytime.
                    </p>
                    {(memoryEntries as MemoryEntry[]).length === 0 ? (
                        <p className="text-black-500 border-black-200 rounded-md border border-dashed px-2 py-2.5 text-center text-[11px]">Nothing remembered yet — it fills in as you work.</p>
                    ) : (
                        <ul className="flex flex-col gap-1">
                            {(memoryEntries as MemoryEntry[]).map((entry) => (
                                <li key={entry.id} className="border-black-100 flex items-start justify-between gap-2 rounded-md border px-2 py-1.5">
                                    <div className="min-w-0">
                                        <p className="text-black-800 text-xs leading-relaxed">{entry.text}</p>
                                        <p className="text-black-400 text-[10px]">{entry.source === 'manual' ? 'Added by you' : 'Learned from a session'}</p>
                                    </div>
                                    <button
                                        type="button"
                                        aria-label={`Forget "${entry.text}"`}
                                        onClick={() => deleteMemoryEntry({ workspace_id: workspace.id, entry_id: entry.id })}
                                        className="text-black-400 mt-0.5 shrink-0 rounded p-0.5 transition-colors hover:bg-[#FBEFEF] hover:text-[#C43D3D]"
                                    >
                                        <X className="h-3 w-3" />
                                    </button>
                                </li>
                            ))}
                        </ul>
                    )}
                    <div className="flex items-center gap-1.5">
                        <input
                            value={memoryDraft}
                            maxLength={300}
                            placeholder="Add a preference…"
                            onChange={(e) => setMemoryDraft(e.target.value)}
                            onKeyDown={(e) => {
                                if (e.key === 'Enter') handleAddMemory();
                            }}
                            className="border-black-200 text-black-900 placeholder:text-black-400 focus:border-brand-500 h-7 w-full rounded-md border bg-white px-2 text-[11px] outline-none transition"
                        />
                        <button type="button" aria-label="Add preference" disabled={!memoryDraft.trim() || isAddingMemory} onClick={handleAddMemory} className="border-black-200 text-black-600 hover:bg-black-100 disabled:text-black-300 flex h-7 w-7 shrink-0 items-center justify-center rounded-md border transition">
                            <Plus className="h-3.5 w-3.5" />
                        </button>
                    </div>
                </div>
            )}

            <div ref={listRef} aria-live="polite" className="flex-1 overflow-y-auto border-t px-3 py-3">
                {turns.length === 0 && !isLoading && (
                    <div className="text-black-500 flex flex-col items-start gap-2 px-1 py-2 text-xs leading-relaxed">
                        <span>Try:</span>
                        {EXAMPLE_PROMPTS.map((prompt) => (
                            <button
                                key={prompt}
                                type="button"
                                onClick={() => send(prompt)}
                                className="border-black-200 hover:border-brand-300 hover:text-black-800 rounded-md border bg-white px-2.5 py-1.5 text-left transition-colors hover:bg-[#F6F9FF]"
                            >
                                “{prompt}”
                            </button>
                        ))}
                    </div>
                )}
                <div className="flex flex-col gap-3">
                    {turns.map((turn, i) =>
                        turn.role === 'user' ? (
                            <div key={i} className="bg-brand-100 text-black-900 ml-6 self-end rounded-lg rounded-br-sm px-3 py-2 text-[13px] leading-relaxed">
                                {turn.content}
                            </div>
                        ) : turn.role === 'review' ? (
                            <div key={i} className="border-black-200 self-stretch rounded-lg border bg-white px-3 py-2.5 text-[13px] leading-relaxed">
                                <div className="text-black-800 flex items-start gap-1.5 font-medium">
                                    <ShieldCheck className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[#0E8A5F]" />
                                    <span>Compliance review</span>
                                </div>
                                <p className="text-black-700 mt-1">{turn.content}</p>
                                {turn.findings?.length === 0 && <p className="mt-1.5 text-xs text-[#0E8A5F]">No issues found.</p>}
                                {!!turn.findings?.length && (
                                    <ul className="border-black-100 mt-2 flex flex-col gap-2 border-t pt-2">
                                        {turn.findings.map((finding, j) => (
                                            <li key={j} className="flex flex-col gap-1">
                                                <div className="flex items-start gap-1.5">
                                                    <span className={`mt-0.5 shrink-0 rounded px-1.5 py-0.5 text-[10px] font-semibold ${SEVERITY_STYLES[finding.severity].chip}`}>{SEVERITY_STYLES[finding.severity].label}</span>
                                                    <span className="text-black-700 text-xs leading-relaxed">{finding.message}</span>
                                                </div>
                                                {finding.fix &&
                                                    (finding.applied ? (
                                                        <span className="ml-1 flex items-center gap-1 text-xs text-[#0E8A5F]">
                                                            <Check className="h-3 w-3" strokeWidth={3} /> Fixed — {finding.fix.description}
                                                        </span>
                                                    ) : (
                                                        <div className="ml-1 flex flex-wrap items-center gap-2">
                                                            <button
                                                                type="button"
                                                                disabled={finding.applying}
                                                                onClick={() => applyFix(i, j)}
                                                                className="border-black-300 text-black-800 hover:bg-black-100 disabled:text-black-400 rounded-md border bg-white px-2 py-0.5 text-[11px] font-medium transition-colors disabled:cursor-wait"
                                                            >
                                                                {finding.applying ? 'Applying…' : `Fix: ${finding.fix.description}`}
                                                            </button>
                                                            {finding.applyError && <span className="text-xs text-[#7A2E2E]">{finding.applyError}</span>}
                                                        </div>
                                                    ))}
                                            </li>
                                        ))}
                                    </ul>
                                )}
                            </div>
                        ) : turn.role === 'memory' ? (
                            <div key={i} className="border-black-200 bg-black-50 self-stretch rounded-md border border-dashed px-3 py-2 text-xs leading-relaxed">
                                {turn.forgotten ? (
                                    <span className="text-black-500">Forgotten — the assistant won&apos;t keep that.</span>
                                ) : (
                                    <>
                                        <span className="text-black-600">
                                            <BookOpen className="mr-1.5 inline h-3 w-3 align-[-1px]" />
                                            Remembered: <span className="text-black-800">“{turn.content}”</span>
                                        </span>
                                        <span className="text-black-400"> · shapes future AI edits</span>
                                        <button type="button" onClick={() => forgetFromNotice(i, turn.entryId!)} className="text-black-600 ml-2 font-medium underline decoration-dotted underline-offset-2 hover:text-[#C43D3D]">
                                            Forget
                                        </button>
                                    </>
                                )}
                            </div>
                        ) : (
                            <div key={i} className={`mr-6 self-start rounded-lg rounded-bl-sm border px-3 py-2 text-[13px] leading-relaxed ${turn.error ? 'border-[#E9CFCF] bg-[#FBEFEF] text-[#7A2E2E]' : 'border-black-200 text-black-800 bg-white'}`}>
                                <div>{turn.content}</div>
                                {turn.error && turn.retryMessage && (
                                    <button type="button" onClick={() => send(turn.retryMessage)} className="mt-1.5 rounded-md border border-[#E9CFCF] bg-white px-2 py-0.5 text-[11px] font-medium text-[#7A2E2E] transition-colors hover:bg-[#FBEFEF]">
                                        Try again
                                    </button>
                                )}
                                {!!turn.results?.length && (
                                    <ul className="border-black-100 mt-2 flex flex-col gap-1 border-t pt-2">
                                        {turn.results.map((result, j) => (
                                            <li key={j} className="flex items-start gap-1.5 text-xs">
                                                {result.ok ? <Check className="mt-0.5 h-3 w-3 shrink-0 text-[#0E8A5F]" strokeWidth={3} /> : <X className="mt-0.5 h-3 w-3 shrink-0 text-[#C43D3D]" strokeWidth={3} />}
                                                <span className={result.ok ? 'text-black-700' : 'text-[#7A2E2E]'}>{result.message}</span>
                                            </li>
                                        ))}
                                    </ul>
                                )}
                            </div>
                        )
                    )}
                    {isLoading && <div className="text-black-500 mr-6 animate-pulse self-start px-1 text-xs">Thinking…</div>}
                    {isReviewing && (
                        <div className="border-black-200 text-black-600 animate-pulse self-stretch rounded-lg border bg-white px-3 py-2.5 text-xs leading-relaxed">
                            <ShieldCheck className="mr-1.5 inline h-3.5 w-3.5 align-[-2px] text-[#0E8A5F]" />
                            Reviewing this form against your organization&apos;s compliance profile and baseline privacy checks — usually under half a minute…
                        </div>
                    )}
                </div>
            </div>

            <div className="border-t p-3">
                <div className="border-black-300 focus-within:border-brand-500 flex items-end gap-2 rounded-lg border bg-white px-2.5 py-2 transition duration-150 focus-within:shadow-[0_0_0_3px_rgba(36,86,204,0.15)]">
                    <textarea
                        rows={2}
                        value={input}
                        maxLength={MAX_MESSAGE_CHARS}
                        placeholder="Describe a change to this form…"
                        onChange={(e) => {
                            setInput(e.target.value);
                            // Grow with the draft, up to max-h-32.
                            e.target.style.height = 'auto';
                            e.target.style.height = `${Math.min(e.target.scrollHeight, 128)}px`;
                        }}
                        onKeyDown={(e) => {
                            if (e.key === 'Enter' && !e.shiftKey) {
                                e.preventDefault();
                                send();
                            }
                        }}
                        className="placeholder:text-black-400 text-black-900 max-h-32 w-full resize-none bg-transparent text-[13px] leading-relaxed outline-none"
                    />
                    <button type="button" aria-label="Send" onClick={() => send()} disabled={isLoading || !input.trim()} className="bg-brand-500 hover:bg-brand-600 disabled:bg-black-300 mb-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-md text-white transition">
                        <Send className="h-3.5 w-3.5" />
                    </button>
                </div>
                <p className="text-black-400 mt-1.5 px-1 text-[10.5px] leading-relaxed">Grounded in your workspace AI profile. Nothing is sent from responses — only this form’s structure.</p>
            </div>
        </div>
    );
}
