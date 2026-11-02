import React, { useEffect, useLayoutEffect, useRef, useState } from 'react';

import { ArrowDown, ArrowUp, Plus, Trash2 } from 'lucide-react';
import i18n from 'i18next';
import { useTranslation } from 'react-i18next';

import {
    CHOICE_TYPES,
    FormOutline,
    LABEL_MAX,
    OutlineQuestion,
    OutlineQuestionType,
    QUESTION_TYPE_LABELS,
    SECTION_TITLE_MAX,
    addQuestion,
    canMove,
    changeType,
    deleteQuestion,
    moveQuestion,
    renameQuestion,
    setChoices,
    setRequired,
    setSectionTitle
} from '@app/utils/ai-outline';

export interface OutlineDeletion {
    previous: FormOutline;
    message: string;
}

interface OutlineReviewProps {
    outline: FormOutline;
    onChange: (outline: FormOutline) => void;
    /** A question was deleted: what the outline was, and what went with it. */
    onDeleted?: (deletion: OutlineDeletion) => void;
    /** Any other edit (ends the chance to undo a deletion). */
    onEdited?: () => void;
    /** Whether Build form lets the AI fill in missing choices. */
    aiFillsGaps?: boolean;
}

const inputClass = 'w-full rounded-md border border-black-300 bg-white px-2 py-1.5 text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500';
const iconButtonClass = 'rounded p-1 text-black-600 hover:bg-black-200 hover:text-black-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 disabled:cursor-not-allowed disabled:opacity-40';

/** Question text that wraps and grows with its content (one paragraph:
 * Enter does not add a line). */
const QuestionText = React.forwardRef<HTMLTextAreaElement, React.TextareaHTMLAttributes<HTMLTextAreaElement>>(function QuestionText({ value, onChange, ...props }, ref) {
    const inner = useRef<HTMLTextAreaElement | null>(null);
    useLayoutEffect(() => {
        const element = inner.current;
        if (!element) return;
        element.style.height = 'auto';
        if (element.scrollHeight) element.style.height = `${element.scrollHeight + 2}px`;
    }, [value]);
    return (
        <textarea
            {...props}
            ref={(element) => {
                inner.current = element;
                if (typeof ref === 'function') ref(element);
                else if (ref) ref.current = element;
            }}
            rows={1}
            value={value}
            className={`${inputClass} resize-none overflow-hidden break-words`}
            onKeyDown={(event) => {
                if (event.key === 'Enter') event.preventDefault();
            }}
            onChange={(event) => {
                event.target.value = event.target.value.replace(/\s*\n\s*/g, ' ');
                onChange?.(event);
            }}
        />
    );
});

function ChoicesEditor({ question, onChange, aiFills }: { question: OutlineQuestion; onChange: (text: string) => void; aiFills: boolean }) {
    const { t } = useTranslation('builder');
    // edited as text, so a blank line while typing is kept until it is used
    const [text, setText] = useState((question.choices ?? []).join('\n'));
    const id = `choices-${question.key}`;
    return (
        <div className="mt-2">
            <label htmlFor={id} className="mb-1 block text-xs text-black-700">
                {t('AI_OUTLINE.CHOICES')}
                {(question.choices ?? []).length < 2 ? (aiFills ? t('AI_OUTLINE.CHOICES_AI') : t('AI_OUTLINE.CHOICES_EMPTY')) : ''}
            </label>
            <textarea
                id={id}
                className={inputClass}
                rows={Math.min(6, Math.max(2, (question.choices ?? []).length + 1))}
                value={text}
                onChange={(event) => {
                    setText(event.target.value);
                    onChange(event.target.value);
                }}
            />
        </div>
    );
}

/** What a deletion took with it, in words. */
export function deletionMessage(before: FormOutline, after: FormOutline): string {
    const rules = before.logic.length - after.logic.length;
    const jumps = before.jumps.length - after.jumps.length;
    const parts = [rules ? i18n.t('builder:AI_OUTLINE.DELETED_RULES', { count: rules }) : '', jumps ? i18n.t('builder:AI_OUTLINE.DELETED_JUMPS', { count: jumps }) : ''].filter(Boolean);
    if (!parts.length) return i18n.t('builder:AI_OUTLINE.DELETED');
    return i18n.t('builder:AI_OUTLINE.DELETED_WITH', { count: rules + jumps, parts: parts.join(i18n.t('builder:AI_OUTLINE.AND')) });
}

export default function OutlineReview({ outline, onChange, onDeleted, onEdited, aiFillsGaps = true }: OutlineReviewProps) {
    const { t } = useTranslation('builder');
    // focus the text of a question just added
    const [focusKey, setFocusKey] = useState<string | null>(null);
    const focusRef = useRef<HTMLTextAreaElement | null>(null);
    useEffect(() => {
        if (focusKey && focusRef.current) {
            focusRef.current.focus();
            setFocusKey(null);
        }
    }, [focusKey]);

    const change = (next: FormOutline) => {
        onEdited?.();
        onChange(next);
    };
    const remove = (key: string) => {
        const next = deleteQuestion(outline, key);
        onChange(next);
        onDeleted?.({ previous: outline, message: deletionMessage(outline, next) });
    };

    // questions are numbered across pages: how many come before each page
    const before = outline.pages.map((_, i) => outline.pages.slice(0, i).reduce((sum, p) => sum + p.questions.length, 0));
    return (
        <div className="flex flex-col gap-4">
            {outline.pages.map((page, pageIndex) => {
                const sectionId = `section-${page.key}`;
                return (
                    <section key={page.key} aria-labelledby={`${sectionId}-heading`} className="rounded-lg border border-black-300 p-2 sm:p-3">
                        <h3 id={`${sectionId}-heading`} className="mb-2 text-xs font-semibold tracking-wide text-black-600 uppercase">
                            {t('AI_OUTLINE.PAGE', { n: pageIndex + 1 })}
                        </h3>
                        <label htmlFor={sectionId} className="text-xs text-black-700">
                            {t('AI_OUTLINE.SECTION_TITLE')}
                        </label>
                        <input id={sectionId} className={inputClass} value={page.sectionTitle ?? ''} maxLength={SECTION_TITLE_MAX} placeholder={t('AI_OUTLINE.SECTION_PLACEHOLDER')} onChange={(event) => change(setSectionTitle(outline, page.key, event.target.value))} />
                        <ol className="mt-3 flex flex-col gap-3">
                            {page.questions.map((question, questionIndex) => {
                                const number = before[pageIndex] + questionIndex + 1;
                                const labelId = `question-${question.key}`;
                                const typeId = `type-${question.key}`;
                                const requiredId = `required-${question.key}`;
                                const name = question.label.trim() || t('AI_OUTLINE.QUESTION_FALLBACK', { n: number });
                                return (
                                    <li key={question.key} className="rounded-md bg-black-100 p-1.5 sm:p-2">
                                        <div className="flex items-start gap-2.5 sm:gap-3">
                                            <span className="mt-1.5 w-4 shrink-0 text-right text-xs text-black-600 sm:w-5" aria-hidden="true">
                                                {number}.
                                            </span>
                                            <div className="flex min-w-0 flex-1 flex-col gap-2">
                                                <label htmlFor={labelId} className="sr-only">
                                                    {t('AI_OUTLINE.QUESTION_N', { n: number })}
                                                </label>
                                                <QuestionText
                                                    id={labelId}
                                                    ref={focusKey === question.key ? focusRef : undefined}
                                                    value={question.label}
                                                    maxLength={LABEL_MAX}
                                                    placeholder={t('AI_OUTLINE.TYPE_THE_QUESTION')}
                                                    onChange={(event) => change(renameQuestion(outline, question.key, event.target.value))}
                                                />
                                                <div className="flex flex-wrap items-center gap-3">
                                                    <label htmlFor={typeId} className="sr-only">
                                                        {t('AI_OUTLINE.TYPE_OF', { n: number })}
                                                    </label>
                                                    <select
                                                        id={typeId}
                                                        className="max-w-full truncate rounded-md border border-black-300 bg-white py-1 pr-8 pl-2 text-xs"
                                                        value={question.type}
                                                        onChange={(event) => change(changeType(outline, question.key, event.target.value as OutlineQuestionType))}
                                                    >
                                                        {(Object.keys(QUESTION_TYPE_LABELS) as OutlineQuestionType[]).map((type) => (
                                                            <option key={type} value={type}>
                                                                {t(`AI_OUTLINE.TYPE.${type}`, { defaultValue: QUESTION_TYPE_LABELS[type] })}
                                                            </option>
                                                        ))}
                                                    </select>
                                                    {question.type !== 'statement' && (
                                                        <label htmlFor={requiredId} className="flex items-center gap-1 text-xs text-black-700">
                                                            <input
                                                                id={requiredId}
                                                                type="checkbox"
                                                                aria-label={t('AI_OUTLINE.REQUIRED_LABEL', { n: number })}
                                                                checked={!!question.required}
                                                                onChange={(event) => change(setRequired(outline, question.key, event.target.checked))}
                                                            />
                                                            {t('AI_OUTLINE.REQUIRED')}
                                                        </label>
                                                    )}
                                                </div>
                                                {question.whyWeAsk && <p className="text-xs text-black-600">{t('AI_OUTLINE.WHY_WE_ASK', { reason: question.whyWeAsk })}</p>}
                                                {CHOICE_TYPES.includes(question.type) && (
                                                    <ChoicesEditor key={`${question.key}-${question.type}`} question={question} aiFills={aiFillsGaps} onChange={(text) => change(setChoices(outline, question.key, text))} />
                                                )}
                                            </div>
                                            <div className="flex shrink-0 items-center">
                                                <button type="button" className={iconButtonClass} aria-label={t('AI_OUTLINE.MOVE_UP', { name })} disabled={!canMove(outline, question.key, -1)} onClick={() => change(moveQuestion(outline, question.key, -1))}>
                                                    <ArrowUp size={16} aria-hidden="true" />
                                                </button>
                                                <button type="button" className={iconButtonClass} aria-label={t('AI_OUTLINE.MOVE_DOWN', { name })} disabled={!canMove(outline, question.key, 1)} onClick={() => change(moveQuestion(outline, question.key, 1))}>
                                                    <ArrowDown size={16} aria-hidden="true" />
                                                </button>
                                                <button type="button" className={iconButtonClass} aria-label={t('AI_OUTLINE.DELETE', { name })} onClick={() => remove(question.key)}>
                                                    <Trash2 size={16} aria-hidden="true" />
                                                </button>
                                            </div>
                                        </div>
                                    </li>
                                );
                            })}
                        </ol>
                        <button
                            type="button"
                            className="mt-2 flex items-center gap-1 rounded px-1 py-1 text-xs font-medium text-brand-600 hover:text-brand-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
                            onClick={() => {
                                const added = addQuestion(outline, page.key);
                                change(added.outline);
                                setFocusKey(added.key);
                            }}
                        >
                            <Plus size={14} aria-hidden="true" /> {t('AI_OUTLINE.ADD_QUESTION', { n: pageIndex + 1 })}
                        </button>
                    </section>
                );
            })}
            {(outline.logic.length > 0 || outline.jumps.length > 0) && (
                <p className="text-xs text-black-600">
                    {t('AI_OUTLINE.LOGIC_ADDED', {
                        count: outline.logic.length + outline.jumps.length,
                        items: [outline.logic.length > 0 ? t('AI_OUTLINE.RULES_COUNT', { count: outline.logic.length }) : '', outline.jumps.length > 0 ? t('AI_OUTLINE.JUMPS_COUNT', { count: outline.jumps.length }) : ''].filter(Boolean).join(t('AI_OUTLINE.AND'))
                    })}
                </p>
            )}
            {outline.omitted && outline.omitted.length > 0 && (
                <div className="text-xs text-black-600">
                    <p className="font-medium text-black-700">{t('AI_OUTLINE.OMITTED')}</p>
                    <ul className="ml-4 list-disc">
                        {outline.omitted.map((item) => (
                            <li key={item.label}>
                                {item.label}: {item.reason}
                            </li>
                        ))}
                    </ul>
                </div>
            )}
        </div>
    );
}

/** The last deletion, with Undo. Kept outside the scrolling list so it is
 * seen wherever the deleted question was; announced to screen readers. */
export function UndoNotice({ deletion, onUndo }: { deletion: OutlineDeletion | null; onUndo: () => void }) {
    const { t } = useTranslation('builder');
    // the deleted question's place is gone: focus moves to Undo
    const undoRef = useRef<HTMLButtonElement | null>(null);
    useEffect(() => {
        if (deletion) undoRef.current?.focus();
    }, [deletion]);
    return (
        // always mounted (a live region must exist before it changes); it
        // takes no space while empty
        <div aria-live="polite">
            {deletion && (
                <div className="mb-3 flex items-center justify-between gap-2 rounded-md bg-black-800 px-3 py-2 text-xs text-white">
                    <span>{deletion.message}</span>
                    <button ref={undoRef} type="button" className="shrink-0 rounded px-1 font-semibold underline focus:outline-none focus-visible:ring-2 focus-visible:ring-white" onClick={onUndo}>
                        {t('AI_OUTLINE.UNDO')}
                    </button>
                </div>
            )}
        </div>
    );
}
