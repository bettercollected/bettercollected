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
 * long the source is. One answer shows its text on the button; several show as removable chips.
 *
 * Keyboard: the button opens the list; in the search box the arrow keys move through the options, Enter chooses,
 * Escape closes (back to the button). A status line says how many choices there are, that none match, or that
 * they could not be loaded. A dependent list that follows an earlier question clears its answer, and says so,
 * when that question's answer changes. The server checks every chosen option again on submission.
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
    const searchRef = useRef<HTMLInputElement>(null);
    const triggerRef = useRef<HTMLButtonElement>(null);
    const [open, setOpen] = useState(false);
    const [query, setQuery] = useState('');
    const [active, setActive] = useState(0);
    const [cleared, setCleared] = useState(false);

    const answer = formResponse.answers?.[field.id];
    const chosen = chosenOptionIds(answer);
    const labels = answerLabels(answer);
    const parentIds = parentOptionIds(field, formResponse.answers);
    const parentLabels = parentLabelsOf(field, formResponse.answers, standardForm?.fields);
    const { items, total, truncated, available, loading, failed, canLoadMore, loadMore } = useSourceOptions(field, { query, parentIds, parentLabels, enabled: open || chosen.length > 0 });

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

    useEffect(() => {
        if (open) searchRef.current?.focus();
    }, [open]);
    useEffect(() => setActive(0), [query, items.length === 0]);

    const choose = (option: { id: string; label: string }) => {
        if (multiple) {
            const selected = chosen.includes(option.id) ? chosen.filter((chosenId) => chosenId !== option.id) : [...chosen, option.id];
            const withLabels = selected.map((selectedId) => ({ id: selectedId, label: selectedId === option.id ? option.label : (labels[selectedId] ?? items.find((item) => item.id === selectedId)?.label ?? '') }));
            if (withLabels.length) addSourcedChoicesAnswer(field.id, withLabels);
            else removeAnswer(field.id);
            return;
        }
        addSourcedChoiceAnswer(field.id, option.id, option.label);
        setOpen(false);
        setQuery('');
        triggerRef.current?.focus();
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
        triggerRef.current?.focus();
    };

    const onSearchKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
        if (event.key === 'ArrowDown') {
            event.preventDefault();
            setActive((index) => Math.min(index + 1, Math.max(items.length - 1, 0)));
        } else if (event.key === 'ArrowUp') {
            event.preventDefault();
            setActive((index) => Math.max(index - 1, 0));
        } else if (event.key === 'Enter') {
            event.preventDefault();
            const option = items[active];
            if (option) choose(option);
        } else if (event.key === 'Escape') {
            event.preventDefault();
            setOpen(false);
            triggerRef.current?.focus();
        } else if (event.key === 'Tab') {
            setOpen(false);
        }
    };

    const shown = chosen.length ? chosen.map((chosenId) => labels[chosenId]).filter(Boolean) : [];
    const buttonText = !multiple && shown[0] ? shown[0] : multiple && shown.length ? t('SOURCE.SELECTED', { count: shown.length }) : t('FIELD.SELECT_OPTION');
    const hasValue = !multiple && !!shown[0];
    const status = failed ? t('SOURCE.FAILED') : !available ? t('SOURCE.NONE') : loading && !items.length ? t('SOURCE.LOADING') : !items.length ? (query ? t('SOURCE.NO_MATCH') : t('SOURCE.NONE')) : t('SOURCE.COUNT', { count: total });
    const otherValue = (multiple ? answer?.choices?.other : answer?.choice?.other) ?? '';

    return (
        <QuestionWrapper field={field}>
            <WithQuestionLabel hints={[noteId, statusId]}>
                {({ label, group }) => (
                    <div className="flex w-full flex-col gap-2">
                        <button
                            ref={triggerRef}
                            type="button"
                            role="combobox"
                            aria-haspopup="listbox"
                            aria-expanded={open}
                            aria-controls={open ? listId : undefined}
                            aria-labelledby={label?.labelledBy}
                            aria-describedby={group['aria-describedby']}
                            aria-readonly={label?.readOnly || undefined}
                            onClick={() => !label?.readOnly && setOpen((value) => !value)}
                            style={{ borderColor: hasValue ? theme?.secondary : (theme?.tertiary ?? '#818CA0'), color: hasValue ? inputTextOf(theme) : '#667085', borderRadius: tokens.fieldRadius }}
                            className="flex min-h-12 w-full cursor-pointer items-center justify-between gap-4 border bg-white px-4 py-3 text-left text-base transition duration-150 lg:text-lg"
                        >
                            <span className="truncate" lang={hasValue ? contentLang : undefined}>
                                {buttonText}
                            </span>
                            <ChevronDown aria-hidden="true" className={cn('h-5 w-5 shrink-0 transition', open && 'rotate-180')} style={{ color: theme?.secondary }} />
                        </button>

                        {open && (
                            <div className="flex flex-col gap-2 border bg-white p-2" style={{ borderColor: theme?.tertiary ?? '#818CA0', borderRadius: tokens.fieldRadius }}>
                                <FieldInput
                                    ref={searchRef}
                                    type="text"
                                    role="combobox"
                                    aria-expanded
                                    aria-controls={listId}
                                    aria-autocomplete="list"
                                    aria-activedescendant={items[active] ? `${id}-opt-${active}` : undefined}
                                    aria-label={t('SOURCE.SEARCH')}
                                    aria-describedby={statusId}
                                    autoComplete="off"
                                    value={query}
                                    onChange={(event: any) => setQuery(event.target.value)}
                                    onKeyDown={onSearchKeyDown}
                                    placeholder={t('SOURCE.SEARCH')}
                                    $formTheme={theme}
                                    className="min-h-11 border px-3 py-2 text-base"
                                    maxLength={100}
                                />
                                <ul id={listId} role="listbox" aria-multiselectable={multiple || undefined} aria-label={t('SOURCE.CHOICES')} className="m-0 max-h-72 list-none overflow-y-auto p-0">
                                    {items.map((option, index) => {
                                        const selected = chosen.includes(option.id);
                                        return (
                                            <li
                                                key={option.id}
                                                id={`${id}-opt-${index}`}
                                                role="option"
                                                aria-selected={selected}
                                                lang={contentLang}
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
                                    <button type="button" disabled={loading} onClick={loadMore} className="min-h-11 self-start rounded-md px-3 text-sm font-medium underline">
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

                        <p id={statusId} role="status" aria-live="polite" aria-atomic="true" className={open || failed || cleared ? 'text-[13px] leading-snug' : 'sr-only'}>
                            {cleared ? (
                                t('SOURCE.CLEARED')
                            ) : open || failed ? (
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
