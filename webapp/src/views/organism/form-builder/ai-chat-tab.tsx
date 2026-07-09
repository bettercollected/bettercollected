'use client';

import { useEffect, useRef, useState } from 'react';

import { Check, Send, X } from 'lucide-react';

import { StandardFormDto } from '@app/models/dtos/form';
import { deepCopy } from '@app/utils/object-utils';
import { selectForm, setForm } from '@app/store/forms/slice';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import useFormFieldsAtom from '@app/store/jotai/field-selectors';
import { useFormState } from '@app/store/jotai/form';
import { useChatEditFormWithAIMutation } from '@app/store/redux/form-api';
import { selectWorkspace } from '@app/store/workspaces/slice';

interface TurnResult {
    ok: boolean;
    message: string;
}

interface ChatTurn {
    role: 'user' | 'assistant';
    content: string;
    results?: TurnResult[];
    error?: boolean;
}

/**
 * The form-editing copilot (plan §2.2). One turn = typed ops applied to the
 * draft server-side; the canvas updates through setFormFields, which records
 * exactly one undo snapshot — so Ctrl+Z reverts a whole AI turn. The per-turn
 * change list comes straight from the backend's OpResults: what the AI
 * actually did, visibly, including what failed.
 */
export default function AIChatTab() {
    const dispatch = useAppDispatch();
    const workspace = useAppSelector(selectWorkspace);
    const standardForm: StandardFormDto = useAppSelector(selectForm);
    const { setFormFields } = useFormFieldsAtom();
    const { setFormState, formState } = useFormState();
    const [chatEdit, { isLoading }] = useChatEditFormWithAIMutation();

    const [turns, setTurns] = useState<ChatTurn[]>([]);
    const [sessionId, setSessionId] = useState<string | null>(null);
    const [input, setInput] = useState('');
    const listRef = useRef<HTMLDivElement>(null);

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
                setFormFields(deepCopy(form.fields ?? []));
                setFormState({ ...formState, title: form.title ?? formState.title });
                dispatch(setForm({ ...standardForm, title: form.title, description: form.description, fields: deepCopy(form.fields ?? []) }));
            }
            setTurns((t) => [...t, { role: 'assistant', content: reply, results }]);
        } else {
            const detail = typeof response.error?.data === 'string' ? response.error.data : 'Something went wrong — nothing was changed. Please try again.';
            setTurns((t) => [...t, { role: 'assistant', content: detail, error: true }]);
        }
        scrollToEnd();
    };

    return (
        <div className="flex h-full flex-col">
            <div className="px-4 pb-3">
                <div className="text-black-600 text-xs font-semibold uppercase tracking-wide">Assistant</div>
                <p className="text-black-600 mt-1 text-xs leading-relaxed">Describe a change — it lands on the canvas, and every change is listed. Undo reverts a whole turn.</p>
            </div>

            <div ref={listRef} className="flex-1 overflow-y-auto border-t px-3 py-3">
                {turns.length === 0 && (
                    <div className="text-black-500 flex flex-col gap-2 px-1 py-2 text-xs leading-relaxed">
                        <span>Try:</span>
                        <span className="border-black-200 rounded-md border bg-white px-2.5 py-1.5">“Add a required work email question on page 1”</span>
                        <span className="border-black-200 rounded-md border bg-white px-2.5 py-1.5">“Make everything on page 2 optional”</span>
                        <span className="border-black-200 rounded-md border bg-white px-2.5 py-1.5">“Rename the form to Customer check-in”</span>
                    </div>
                )}
                <div className="flex flex-col gap-3">
                    {turns.map((turn, i) =>
                        turn.role === 'user' ? (
                            <div key={i} className="bg-brand-100 text-black-900 ml-6 self-end rounded-lg rounded-br-sm px-3 py-2 text-[13px] leading-relaxed">
                                {turn.content}
                            </div>
                        ) : (
                            <div key={i} className={`mr-6 self-start rounded-lg rounded-bl-sm border px-3 py-2 text-[13px] leading-relaxed ${turn.error ? 'border-[#E9CFCF] bg-[#FBEFEF] text-[#7A2E2E]' : 'border-black-200 text-black-800 bg-white'}`}>
                                <div>{turn.content}</div>
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
                    {isLoading && <div className="text-black-500 mr-6 self-start px-1 text-xs">Thinking…</div>}
                </div>
            </div>

            <div className="border-t p-3">
                <div className="border-black-300 focus-within:border-brand-500 flex items-end gap-2 rounded-lg border bg-white px-2.5 py-2 transition duration-150 focus-within:shadow-[0_0_0_3px_rgba(36,86,204,0.15)]">
                    <textarea
                        rows={2}
                        value={input}
                        disabled={isLoading}
                        placeholder="Describe a change to this form…"
                        onChange={(e) => setInput(e.target.value)}
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
