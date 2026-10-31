import { useId, useRef, useState } from 'react';

import { X } from 'lucide-react';

import useRespondentLanguage from '@app/lib/hooks/use-respondent-language';
import { StandardFormFieldDto } from '@app/models/dtos/form';
import { FieldInput } from '@app/shadcn/components/ui/input';
import { cn } from '@app/shadcn/util/lib';
import { useFormState } from '@app/store/jotai/form';
import { useFormResponse } from '@app/store/jotai/responder-form-response';
import { tagLimits } from '@app/utils/answer-rules';
import { answerTags, isTag, tagKey, tagLength } from '@app/utils/tags';
import { styleTokens } from '@app/views/molecules/theme/theme-shared';

import { useEnterToNextQuestion } from './next-question';
import { joinIds, useQuestionLabel } from './question-label-context';
import QuestionWrapper from './question-wrapper';

interface ITagsField {
    field: StandardFormFieldDto;
    slide?: StandardFormFieldDto;
    isBuilder?: boolean;
}

/** What one try at adding tags did: the tags now, and why one was refused (the rest are kept). */
export interface TagsAdded {
    tags: string[];
    added: string[];
    refusal?: { reason: 'duplicate' | 'too_long' | 'too_many' | 'format'; tag: string };
}

/**
 * Add the tags in `raw` (separated by commas, semicolons or line breaks) to
 * `tags`: each is trimmed, an empty one is ignored, and one that repeats a tag
 * already there (ignoring case), is too long, is not a well-formed tag or
 * would pass the most the question takes is refused, with the first such
 * reason reported. The tags before a refused one are kept.
 */
export function addTags(tags: string[], raw: string, field: StandardFormFieldDto): TagsAdded {
    const limits = tagLimits(field);
    const next = [...tags];
    const added: string[] = [];
    for (const part of raw.split(/[,;\n\r]/)) {
        const tag = part.trim();
        if (!tag) continue;
        if (!isTag(tag)) return { tags: next, added, refusal: { reason: 'format', tag } };
        if (tagLength(tag) > limits.length) return { tags: next, added, refusal: { reason: 'too_long', tag } };
        if (next.some((existing) => tagKey(existing) === tagKey(tag))) return { tags: next, added, refusal: { reason: 'duplicate', tag } };
        if (next.length >= limits.most) return { tags: next, added, refusal: { reason: 'too_many', tag } };
        next.push(tag);
        added.push(tag);
    }
    return { tags: next, added };
}

/**
 * A tags question: a text box and the tags entered so far as removable chips.
 * Enter, a comma or a semicolon turns the typed text into a tag (trimmed;
 * nothing for empty text; a repeat, ignoring case, is refused, as is a tag past
 * the longest or the most the question takes). Backspace in the empty box
 * removes the last tag; every chip has its own "Remove <tag>" button. A status
 * region says what was added, removed or refused. Text left in the box when it
 * loses focus is added too, so nothing typed is lost.
 */
function TagsFieldSection({ field, isBuilder }: ITagsField) {
    const { theme } = useFormState();
    const { formResponse, addFieldTagsAnswer, removeAnswer } = useFormResponse();
    const { t } = useRespondentLanguage();
    const onKeyDown = useEnterToNextQuestion(field);
    const tags = answerTags(formResponse.answers?.[field.id]) ?? [];
    const limits = tagLimits(field);
    const [draft, setDraft] = useState('');
    const [status, setStatus] = useState<{ text: string; refusal: boolean }>({ text: '', refusal: false });
    const inputRef = useRef<HTMLInputElement>(null);
    const id = useId();
    const inputId = `tags-input-${field.id}`;
    const labelId = `${id}-label`;
    const hintId = `${id}-hint`;
    const countId = `${id}-count`;
    const statusId = `${id}-status`;
    const hasMax = field.validations?.maxChoices !== undefined && field.validations?.maxChoices !== null;
    const hasMin = limits.fewest > 0;
    const { label: question, control } = useQuestionLabel(hintId, hasMax && countId, statusId);
    const labelledBy = question?.labelledBy ? joinIds(question.labelledBy, labelId) : undefined;

    const save = (next: string[]) => {
        if (next.length) addFieldTagsAnswer(field.id, next);
        else removeAnswer(field.id);
    };

    const refusalText = (refusal: NonNullable<TagsAdded['refusal']>): string => {
        switch (refusal.reason) {
            case 'duplicate':
                return t('TAGS.DUPLICATE', { tag: refusal.tag });
            case 'too_long':
                return t('RULE.TAG_TOO_LONG', { count: limits.length });
            case 'too_many':
                return t('TAGS.AT_MOST', { count: limits.most });
            default:
                return t('RULE.FORMAT_TAGS');
        }
    };

    /** Add what is in `raw`; the part that is refused stays in the box. Returns whether nothing was refused. */
    const commit = (raw: string): boolean => {
        if (!raw.trim()) return true;
        const result = addTags(tags, raw, field);
        if (result.added.length) save(result.tags);
        if (result.refusal) {
            // keep the text of the refused tag (and what follows it) to fix
            const at = raw.toLowerCase().indexOf(result.refusal.tag.toLowerCase());
            setDraft(at >= 0 ? raw.slice(at) : result.refusal.tag);
            setStatus({ text: refusalText(result.refusal), refusal: true });
            return false;
        }
        setDraft('');
        setStatus({ text: result.added.length ? t('TAGS.ADDED', { tag: result.added[result.added.length - 1], count: result.tags.length }) : '', refusal: false });
        return true;
    };

    const remove = (index: number) => {
        const [gone] = tags.slice(index, index + 1);
        save(tags.filter((_tag, position) => position !== index));
        setStatus({ text: t('TAGS.REMOVED', { tag: gone, count: tags.length - 1 }), refusal: false });
        inputRef.current?.focus();
    };

    const fieldRadius = styleTokens(theme?.style).fieldRadius;
    const chipStyle = { borderRadius: fieldRadius, borderColor: theme?.tertiary ?? '#818CA0', color: theme?.primary };

    return (
        <div className="flex flex-col gap-2">
            {tags.length > 0 && (
                <ul aria-label={t('TAGS.LIST')} className="m-0 flex list-none flex-wrap gap-2 p-0">
                    {tags.map((tag, index) => (
                        <li key={tag} className="flex min-h-9 items-center gap-1 border bg-white py-1 pr-1 pl-3 text-base" style={chipStyle}>
                            <span className="[overflow-wrap:anywhere]">{tag}</span>
                            <button type="button" disabled={isBuilder} aria-label={t('TAGS.REMOVE', { tag })} className="flex h-7 w-7 shrink-0 cursor-pointer items-center justify-center rounded" onClick={() => remove(index)}>
                                <X className="h-4 w-4" aria-hidden="true" />
                            </button>
                        </li>
                    ))}
                </ul>
            )}
            <div className="flex flex-col gap-1">
                <label id={labelId} htmlFor={inputId} className="text-sm font-medium" style={{ color: theme?.primary }}>
                    {t('TAGS.ADD')}
                </label>
                <FieldInput
                    {...control}
                    ref={inputRef}
                    id={inputId}
                    type="text"
                    autoComplete="off"
                    autoCapitalize="off"
                    spellCheck={false}
                    enterKeyHint="enter"
                    placeholder={t('TAGS.PLACEHOLDER')}
                    value={draft}
                    disabled={isBuilder}
                    aria-labelledby={labelledBy}
                    $formTheme={theme}
                    onChange={(event: React.ChangeEvent<HTMLInputElement>) => {
                        const value = event.target.value;
                        // a comma or a semicolon (typed, or in pasted text) ends a tag
                        if (/[,;\n\r]/.test(value)) commit(value);
                        else setDraft(value);
                    }}
                    onKeyDown={(event: React.KeyboardEvent<HTMLInputElement>) => {
                        if (event.nativeEvent.isComposing) return;
                        if (event.key === ',' || event.key === ';') {
                            event.preventDefault();
                            commit(draft);
                            return;
                        }
                        if (event.key === 'Enter') {
                            if (draft.trim()) {
                                event.preventDefault();
                                commit(draft);
                            } else onKeyDown(event);
                            return;
                        }
                        if (event.key === 'Backspace' && draft === '' && tags.length) {
                            event.preventDefault();
                            remove(tags.length - 1);
                        }
                    }}
                    onBlur={() => {
                        if (draft.trim()) commit(draft);
                    }}
                    className="min-h-12"
                />
            </div>
            <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 text-sm text-[#667085]">
                <span id={hintId}>{hasMin ? t('TAGS.HINT_MIN', { count: limits.fewest }) : t('TAGS.HINT')}</span>
                {hasMax && <span id={countId}>{t('TAGS.COUNT', { count: tags.length, max: limits.most })}</span>}
            </div>
            {/* What was added, removed or refused: announced politely, and shown when it is a refusal. */}
            <p id={statusId} role="status" className={cn(status.refusal ? 'text-[15px] leading-snug font-medium' : 'sr-only')} style={status.refusal ? { color: theme?.primary } : undefined}>
                {status.text}
            </p>
        </div>
    );
}

const TagsField = ({ field, slide, isBuilder = false }: ITagsField) =>
    isBuilder ? (
        <TagsFieldSection field={field} slide={slide} isBuilder />
    ) : (
        <QuestionWrapper field={field}>
            <TagsFieldSection field={field} slide={slide} />
        </QuestionWrapper>
    );

export default TagsField;
