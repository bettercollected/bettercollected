'use client';

import { useEffect, useRef } from 'react';

import { Check, Eye, EyeOff, X } from 'lucide-react';

import { AIProposal, ProposalChangeGroup, acceptableOps, toggleOp } from '@app/utils/ai-proposal';

export type ProposalStatus = 'pending' | 'accepting' | 'accepted' | 'discarded' | 'superseded' | 'stale' | 'closed' | 'expired';

export interface ProposalOpError {
    index: number;
    message: string;
}

interface Props {
    proposal: AIProposal;
    groups: ProposalChangeGroup[];
    status: ProposalStatus;
    selected: number[];
    error?: string;
    opErrors?: ProposalOpError[];
    appliedCount?: number;
    previewing: boolean;
    /** Move focus here when the proposal arrives. */
    autoFocus?: boolean;
    onSelect: (selected: number[]) => void;
    onAccept: (opIndexes?: number[]) => void;
    onDiscard: () => void;
    onTogglePreview: () => void;
    onShowPage?: (pageId: string) => void;
}

const CLOSED_TEXT: Partial<Record<ProposalStatus, string>> = {
    discarded: 'Discarded. Nothing was changed.',
    superseded: 'Replaced by a newer proposal. Nothing was changed.',
    stale: 'Not applied: the form changed since this was proposed. Ask again to get a new proposal.',
    closed: 'This proposal was already handled elsewhere. Nothing was changed here.',
    expired: 'This proposal expired. Ask again to get a new one.'
};

/**
 * One AI proposal in the chat: the change list grouped by page, a checkbox
 * per change (changes made by the same operation are chosen together), and
 * Accept all / Accept selected / Discard. Nothing is saved until accepted.
 */
export default function AIProposalCard({ proposal, groups, status, selected, error, opErrors, appliedCount, previewing, autoFocus, onSelect, onAccept, onDiscard, onTogglePreview, onShowPage }: Props) {
    const headingRef = useRef<HTMLHeadingElement>(null);
    const headingId = `ai-proposal-${proposal.id}`;
    const all = acceptableOps(proposal);
    const open = status === 'pending' || status === 'accepting';
    const busy = status === 'accepting';
    const failed = (proposal.results ?? []).filter((result) => !result.ok);
    const errorsByOp = new Map((opErrors ?? []).map((e) => [e.index, e.message]));

    useEffect(() => {
        if (autoFocus) headingRef.current?.focus();
    }, [autoFocus]);

    const allSelected = selected.length === all.length;

    return (
        <section aria-labelledby={headingId} className="mt-2 border-t border-black-100 pt-2" data-testid="ai-proposal">
            <h3 id={headingId} ref={headingRef} tabIndex={-1} className="text-xs font-semibold text-black-800 outline-hidden focus-visible:ring-2 focus-visible:ring-brand-500">
                {open ? 'Proposed changes' : status === 'accepted' ? 'Applied changes' : 'Proposed changes (not applied)'}
            </h3>
            {status === 'accepted' && (
                <p className="mt-1 flex items-center gap-1 text-xs text-success-700">
                    <Check className="h-3 w-3" strokeWidth={3} aria-hidden="true" />
                    Applied {appliedCount ?? all.length} of {all.length} change{all.length === 1 ? '' : 's'}. Undo reverts them.
                </p>
            )}
            {!open && CLOSED_TEXT[status] && <p className="mt-1 text-xs text-black-600">{CLOSED_TEXT[status]}</p>}
            {groups.map((group) => {
                const groupHeadingId = `${headingId}-${group.key}`;
                return (
                    <div key={group.key} className="mt-2">
                        <div className="flex items-center justify-between gap-2">
                            <h4 id={groupHeadingId} className="text-[11px] font-semibold uppercase tracking-wide text-black-600">
                                {group.label}
                            </h4>
                            {open && group.pageId && onShowPage && (
                                <button type="button" onClick={() => onShowPage(group.pageId!)} className="text-[11px] font-medium text-brand-600 underline decoration-dotted underline-offset-2 hover:text-brand-500">
                                    Preview page
                                </button>
                            )}
                        </div>
                        <ul aria-labelledby={groupHeadingId} className="mt-1 flex flex-col gap-1">
                            {group.changes.map((change) => {
                                const checkboxId = `${headingId}-change-${change.key}`;
                                const opError = errorsByOp.get(change.opIndex);
                                return (
                                    <li key={change.key} className="text-xs leading-relaxed">
                                        <div className="flex items-start gap-1.5">
                                            <input
                                                id={checkboxId}
                                                type="checkbox"
                                                className="mt-0.5 h-3.5 w-3.5 shrink-0"
                                                checked={status === 'accepted' ? true : selected.includes(change.opIndex)}
                                                disabled={!open || busy}
                                                onChange={(e) => onSelect(toggleOp(proposal, selected, change.opIndex, e.target.checked))}
                                            />
                                            <label htmlFor={checkboxId} className={open ? 'cursor-pointer text-black-700' : 'text-black-600'}>
                                                {change.text}
                                            </label>
                                        </div>
                                        {opError && <p className="ml-5 text-[#7A2E2E]">{opError}</p>}
                                    </li>
                                );
                            })}
                        </ul>
                    </div>
                );
            })}
            {failed.length > 0 && (
                <div className="mt-2">
                    <h4 className="text-[11px] font-semibold uppercase tracking-wide text-black-600">Could not be made</h4>
                    <ul className="mt-1 flex flex-col gap-1">
                        {failed.map((result) => (
                            <li key={result.index} className="flex items-start gap-1.5 text-xs text-[#7A2E2E]">
                                <X className="mt-0.5 h-3 w-3 shrink-0" strokeWidth={3} aria-hidden="true" />
                                <span>{result.message}</span>
                            </li>
                        ))}
                    </ul>
                </div>
            )}
            {error && (
                <p role="alert" className="mt-2 text-xs text-[#7A2E2E]">
                    {error}
                </p>
            )}
            {open && (
                <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
                    <button
                        type="button"
                        disabled={busy}
                        onClick={() => onAccept()}
                        className="rounded-md bg-action px-2.5 py-1 text-[11px] font-medium text-white transition hover:bg-action-hover disabled:cursor-wait disabled:bg-black-300"
                    >
                        {busy ? 'Applying…' : 'Accept all'}
                    </button>
                    <button
                        type="button"
                        disabled={busy || selected.length === 0}
                        onClick={() => onAccept(allSelected ? undefined : selected)}
                        className="rounded-md border border-black-300 bg-white px-2.5 py-1 text-[11px] font-medium text-black-800 transition-colors disabled:text-black-400 hover:bg-black-100"
                    >
                        Accept selected ({selected.length})
                    </button>
                    <button type="button" disabled={busy} onClick={onDiscard} className="rounded-md border border-black-300 bg-white px-2.5 py-1 text-[11px] font-medium text-black-800 transition-colors disabled:text-black-400 hover:bg-black-100">
                        Discard
                    </button>
                    <button
                        type="button"
                        aria-pressed={previewing}
                        onClick={onTogglePreview}
                        className={`ml-auto flex items-center gap-1 rounded-md border px-2 py-1 text-[11px] font-medium transition-colors ${previewing ? 'border-brand-200 bg-brand-100 text-brand-600' : 'border-black-300 bg-white text-black-600 hover:bg-black-100'}`}
                    >
                        {previewing ? <EyeOff className="h-3 w-3" aria-hidden="true" /> : <Eye className="h-3 w-3" aria-hidden="true" />}
                        Preview
                    </button>
                </div>
            )}
        </section>
    );
}
