'use client';

import { KeyboardEvent, useEffect, useId, useRef, useState } from 'react';

import { Check, ChevronDown, Loader2, X } from 'lucide-react';

import useFormContentLanguage from '@app/lib/hooks/use-form-content-language';
import useRespondentLanguage from '@app/lib/hooks/use-respondent-language';
import { useSourceOptions } from '@app/lib/hooks/use-source-options';
import { StandardFormFieldDto } from '@app/models/dtos/form';
import { FieldInput } from '@app/shadcn/components/ui/input';
import { cn } from '@app/shadcn/util/lib';
import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { useFormState } from '@app/store/jotai/form';
import { useGroupItemScope } from '@app/store/jotai/group-item-scope';
import { useFormResponse } from '@app/store/jotai/responder-form-response';
import { answerLabels, chosenOptionIds, isAnswersSource, parentKey, parentLabelsOf, parentOptionIds } from '@app/utils/option-sources';
import { moveOnFrom } from '@app/utils/scroll-utils';
import { inputTextOf } from '@app/views/molecules/theme/theme-root';
import { styleTokens } from '@app/views/molecules/theme/theme-shared';

import { WithQuestionLabel } from './question-label-context';
import QuestionWrapper from './question-wrapper';

interface Props {
    field: StandardFormFieldDto;
    slideIndex: number;
}

/**
 * A dropdown or multiple choice question whose options come from a workspace list or from another form's answers
 * (utils/option-sources.ts). The options are not in the form: they are fetched from the server a page at a time
 * as the respondent opens the list and types (labels only), so the control is always a searchable list, however
 * long the source is.
 *
 * One ARIA combobox (the WAI-ARIA "editable combobox with list autocomplete"): a text box that shows the chosen
 * text and, while the list is open, what is being searched for, and a listbox popup under it. The list opens on
 * a click, on typing or on the down arrow; the arrow keys move through the options (Home, End, Page Up and Page
 * Down too, once the list is being walked), Enter chooses, Escape closes, Tab closes (and chooses the option the
 * respondent walked to, for a single choice), a click outside closes. Several choices show as removable chips.
 * A status line says how many choices there are, that none match, that the server asked for a pause or that they
 * could not be loaded. A dependent list that follows an earlier question clears its answer, and says so, when that
 * question's answer changes. The server checks every chosen option again on submission.
 */
export default function SourceOptionsField({ field, slideIndex }: Props) {
    const multiple = !!field.properties?.allowMultipleSelection && String(field.type) === 'multiple_choice';
    const { theme } = useFormState();
    const { t } = useRespondentLanguage();
    const contentLang = useFormContentLanguage();
    const { formResponse, addSourcedChoiceAnswer, addSourcedChoicesAnswer, addOtherChoiceAnswer, addOtherChoicesAnswer, removeAnswer } = useFormResponse();
    const inGroup = !!useGroupItemScope();
    const standardForm = useAppSelector(selectForm);
    const tokens = styleTokens(theme?.style);
    const id = useId();
    const listId = `${id}-list`;
    const statusId = `${id}-status`;
    const noteId = `${id}-note`;
    const boxRef = useRef<HTMLDivElement>(null);
    const inputRef = useRef<HTMLInputElement>(null);
    const [open, setOpen] = useState(false);
    const [query, setQuery] = useState('');
    // the option the arrow keys are on (-1: none yet) and whether the respondent walked the list
    const [active, setActive] = useState(-1);
    const [walked, setWalked] = useState(false);
    const [cleared, setCleared] = useState(false);

    const answer = formResponse.answers?.[field.id];
    const chosen = chosenOptionIds(answer);
    const labels = answerLabels(answer);
    const parentIds = parentOptionIds(field, formResponse.answers);
    const parentLabels = parentLabelsOf(field, formResponse.answers, standardForm?.fields);
    const { items, total, truncated, available, loading, failed, limited, canLoadMore, loadMore } = useSourceOptions(field, { query, parentIds, parentLabels, enabled: open || chosen.length > 0 });

    // A dependent list follows the question it depends on: when that answer changes, a choice made under the old one goes.
    const followed = parentKey(parentIds);
    const previous = useRef(followed);
    useEffect(() => {
        if (previous.current === followed) return;
        previous.current = followed;
        if (chosen.length) {
            removeAnswer(field.id);
            setCleared(true);
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [followed]);
    useEffect(() => {
        if (chosen.length) setCleared(false);
    }, [chosen.length]);

    // a click outside the control closes the list
    useEffect(() => {
        if (!open) return;
        const away = (event: MouseEvent) => {
            if (!boxRef.current?.contains(event.target as Node)) close();
        };
        document.addEventListener('mousedown', away);
        return () => document.removeEventListener('mousedown', away);
    }, [open]);

    const close = () => {
        setOpen(false);
        setQuery('');
        setActive(-1);
        setWalked(false);
    };
    const show = () => {
        setOpen(true);
    };
    // new options start with none walked to
    useEffect(() => {
        setActive(-1);
        setWalked(false);
    }, [query]);

    const withLabel = (optionId: string, fallback?: string) => labels[optionId] ?? fallback ?? items.find((item) => item.id === optionId)?.label ?? '';

    const choose = (option: { id: string; label: string }) => {
        if (multiple) {
            const selected = chosen.includes(option.id) ? chosen.filter((chosenId) => chosenId !== option.id) : [...chosen, option.id];
            const withLabels = selected.map((selectedId) => ({ id: selectedId, label: selectedId === option.id ? option.label : withLabel(selectedId) }));
            if (withLabels.length) addSourcedChoicesAnswer(field.id, withLabels);
            else removeAnswer(field.id);
            return;
        }
        addSourcedChoiceAnswer(field.id, option.id, option.label);
        close();
        inputRef.current?.focus();
        setTimeout(() => {
            // on to the next question, as the other single choice controls do
            const questions = standardForm?.fields?.[slideIndex]?.properties?.fields;
            if (questions?.length !== field.index + 1) moveOnFrom(field.id, questions?.[field.index + 1]?.id);
        }, 200);
    };

    const remove = (optionId: string) => {
        const rest = chosen.filter((chosenId) => chosenId !== optionId).map((chosenId) => ({ id: chosenId, label: labels[chosenId] ?? '' }));
        if (rest.length) addSourcedChoicesAnswer(field.id, rest);
        else removeAnswer(field.id);
        inputRef.current?.focus();
    };

    const walk = (to: number) => {
        setActive(Math.max(0, Math.min(to, items.length - 1)));
        setWalked(true);
    };

    const onKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
        switch (event.key) {
            case 'ArrowDown':
                event.preventDefault();
                if (!open) return show();
                // past the last option: the next page, when there is one
                if (active >= items.length - 1 && canLoadMore) return loadMore();
                return walk(active + 1);
            case 'ArrowUp':
                event.preventDefault();
                if (!open) return show();
                return walk(active <= 0 ? 0 : active - 1);
            case 'Home':
            case 'End':
                // in the list once it is walked; otherwise the cursor moves in the text, as in any text box
                if (open && walked && items.length) {
                    event.preventDefault();
                    walk(event.key === 'Home' ? 0 : items.length - 1);
                }
                return;
            case 'PageDown':
            case 'PageUp':
                if (open && items.length) {
                    event.preventDefault();
                    walk((active < 0 ? 0 : active) + (event.key === 'PageDown' ? 10 : -10));
                }
                return;
            case 'Enter':
                if (open) {
                    // Enter in an open list never submits the page
                    event.preventDefault();
                    if (items[active]) choose(items[active]);
                }
                return;
            case 'Escape':
                if (open) {
                    event.preventDefault();
                    close();
                }
                return;
            case 'Tab':
                // leaving the box: a single choice takes the option that was walked to; the list closes
                if (open && !multiple && walked && items[active]) choose(items[active]);
                else if (open) close();
                return;
            default:
        }
    };

    const shown = chosen.map((chosenId) => labels[chosenId]).filter(Boolean);
    const single = !multiple && shown[0] ? shown[0] : '';
    const hasValue = !!single;
    const status = limited
        ? t('SOURCE.LIMITED')
        : failed
          ? t('SOURCE.FAILED')
          : !available
            ? t('SOURCE.NONE')
            : loading && !items.length
              ? t('SOURCE.LOADING')
              : !items.length
                ? query
                    ? t('SOURCE.NO_MATCH')
                    : t('SOURCE.NONE')
                : t('SOURCE.COUNT', { count: total });
    const otherValue = (multiple ? answer?.choices?.other : answer?.choice?.other) ?? '';
    const visibleStatus = open || failed || limited || cleared;

    return (
        <QuestionWrapper field={field}>
            <WithQuestionLabel hints={[noteId, statusId]}>
                {({ label, group }) => (
                    <div ref={boxRef} className="flex w-full flex-col gap-2">
                        <div className="relative">
                            <FieldInput
                                ref={inputRef}
                                type="text"
                                role="combobox"
                                aria-expanded={open}
                                aria-controls={open ? listId : undefined}
                                aria-haspopup="listbox"
                                aria-autocomplete="list"
                                aria-activedescendant={open && items[active] ? `${id}-opt-${active}` : undefined}
                                aria-labelledby={label?.labelledBy}
                                aria-describedby={group['aria-describedby']}
                                aria-required={label?.required || undefined}
                                aria-invalid={label?.invalid || undefined}
                                aria-readonly={label?.readOnly || undefined}
                                readOnly={label?.readOnly}
                                autoComplete="off"
                                maxLength={100}
                                // the chosen text when closed; what is searched for while open
                                value={open ? query : single}
                                placeholder={open && single ? single : t('FIELD.SELECT_OPTION')}
                                lang={!open && hasValue ? contentLang : undefined}
                                onChange={(event: any) => {
                                    if (label?.readOnly) return;
                                    setQuery(event.target.value);
                                    show();
                                }}
                                onClick={() => !label?.readOnly && show()}
                                onKeyDown={onKeyDown}
                                $formTheme={theme}
                                style={{ borderColor: hasValue ? theme?.secondary : (theme?.tertiary ?? '#818CA0'), color: hasValue && !open ? inputTextOf(theme) : undefined, borderRadius: tokens.fieldRadius }}
                                className="min-h-12 w-full border bg-white py-3 pr-12 pl-4 text-base lg:text-lg"
                            />
                            <ChevronDown aria-hidden="true" className={cn('pointer-events-none absolute top-1/2 right-4 h-5 w-5 -translate-y-1/2 transition', open && 'rotate-180')} style={{ color: theme?.secondary }} />
                        </div>

                        {open && (
                            <div className="flex flex-col gap-1 border bg-white p-1" style={{ borderColor: theme?.tertiary ?? '#818CA0', borderRadius: tokens.fieldRadius }}>
                                <ul id={listId} role="listbox" aria-multiselectable={multiple || undefined} aria-labelledby={label?.labelledBy} className="m-0 max-h-72 list-none overflow-y-auto p-0">
                                    {items.map((option, index) => {
                                        const selected = chosen.includes(option.id);
                                        return (
                                            <li
                                                key={option.id}
                                                id={`${id}-opt-${index}`}
                                                role="option"
                                                aria-selected={selected}
                                                lang={contentLang}
                                                // the text box keeps the focus while the list is used
                                                onMouseDown={(event) => event.preventDefault()}
                                                onClick={() => choose(option)}
                                                onMouseMove={() => setActive(index)}
                                                className={cn('flex min-h-11 cursor-pointer items-center justify-between gap-3 rounded-sm px-3 py-2 text-base', index === active && 'bg-black-100')}
                                            >
                                                <span className="break-words">{option.label}</span>
                                                {selected && <Check aria-hidden="true" className="h-4 w-4 shrink-0" />}
                                            </li>
                                        );
                                    })}
                                </ul>
                                {canLoadMore && (
                                    <button type="button" tabIndex={-1} disabled={loading} onMouseDown={(event) => event.preventDefault()} onClick={loadMore} className="min-h-11 self-start rounded-md px-3 text-sm font-medium underline">
                                        {t('SOURCE.MORE')}
                                    </button>
                                )}
                            </div>
                        )}

                        {multiple && shown.length > 0 && (
                            <ul aria-label={t('SOURCE.SELECTED_LIST')} className="m-0 flex list-none flex-wrap gap-2 p-0">
                                {chosen.map((chosenId) => (
                                    <li key={chosenId} className="flex min-h-9 items-center gap-1 border bg-white py-1 pr-1 pl-3 text-base" style={{ borderRadius: tokens.fieldRadius, borderColor: theme?.tertiary ?? '#818CA0' }}>
                                        <span lang={contentLang}>{labels[chosenId]}</span>
                                        <button type="button" aria-label={t('SOURCE.REMOVE', { option: labels[chosenId] })} onClick={() => remove(chosenId)} className="flex h-8 w-8 items-center justify-center rounded-full">
                                            <X aria-hidden="true" className="h-4 w-4" />
                                        </button>
                                    </li>
                                ))}
                            </ul>
                        )}

                        <p id={statusId} role="status" aria-live="polite" aria-atomic="true" className={visibleStatus ? 'text-[13px] leading-snug' : 'sr-only'}>
                            {cleared ? (
                                t('SOURCE.CLEARED')
                            ) : open || failed || limited ? (
                                <span className="inline-flex items-center gap-2">
                                    {loading && <Loader2 aria-hidden="true" className="h-3.5 w-3.5 animate-spin" />}
                                    {status}
                                    {truncated && open ? ` ${t('SOURCE.CUT')}` : ''}
                                </span>
                            ) : null}
                        </p>
                        {isAnswersSource(field.properties?.optionSource) && !inGroup && (
                            <p id={noteId} className="text-[13px] leading-snug opacity-80">
                                {t('SOURCE.ANSWERS_NOTE')}
                            </p>
                        )}
                        {field.properties?.allowOtherChoice && (
                            <FieldInput
                                type="text"
                                value={otherValue}
                                placeholder={t('FIELD.OTHER_CHOICE')}
                                aria-label={t('FIELD.OTHER')}
                                onChange={(event: any) => (multiple ? addOtherChoicesAnswer(field.id, event.target.value) : addOtherChoiceAnswer(field.id, event.target.value))}
                                $formTheme={theme}
                                className="flex min-h-12 justify-between border px-4 py-3 text-base"
                            />
                        )}
                    </div>
                )}
            </WithQuestionLabel>
        </QuestionWrapper>
    );
}
