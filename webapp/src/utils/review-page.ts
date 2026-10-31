import { format } from 'date-fns';
import { nl as dutch } from 'date-fns/locale/nl';

import type { FieldRuleStates } from '@app/lib/field-rules';
import { FieldTypes, StandardFormDto, StandardFormFieldDto } from '@app/models/dtos/form';
import { JUMP_TARGET_SUBMIT } from '@app/models/types/form-builder-shared';
import { PipeContext, resolvePipesInText, resolvePipesInTitle, stringTitleToDoc } from '@app/utils/answer-piping';
import { calculatedAnswerValue, formatCalculatedValue, isShownToRespondents } from '@app/utils/calculated-fields';
import { LogicSources, choiceAnswerText, getComparableAnswerValue, getHiddenFieldIds, logicSourcesById, resolveJump } from '@app/utils/conditional-logic';
import { isoToLocalDate } from '@app/utils/date-rules';
import { legacyTitleText } from '@app/utils/legacy-title';
import { pageInvalidations } from '@app/utils/page-validation';
import { getGroupChildren, getGroupItems, getItemHeader, getItemHiddenChildIds, hasAnswerValue, isRepeatingGroup, itemScopeAnswers, normalizeGroupAnswersForSubmit, scopedFieldId } from '@app/utils/repeating-groups';
import { plainTextFromJson } from '@app/utils/richTextEditorExtenstion/get-html-from-json';

/**
 * The review page (an optional page after the last one, where respondents
 * read their answers before sending them). It is a place in the respondent's
 * journey like the welcome page (-1) and the ending (-2), never a page of the
 * form, and lives in the browser only: nothing is stored or sent until the
 * respondent submits from it.
 */
export const REVIEW_SLIDE = -3;

/** Does this form show respondents a review page before they submit? */
export const isReviewEnabled = (form?: Pick<StandardFormDto, 'settings' | 'fields' | 'unavailable'> | null): boolean => !!form?.settings?.showReviewPage && !form?.unavailable && !!form?.fields?.length;

/** The pages of a respondent's history, in order, each once (the welcome page and the review are not pages). */
export function pathPages(history: ReadonlyArray<number> | undefined): number[] {
    return [...new Set((history ?? []).filter((slide) => slide >= 0))];
}

type Translate = (key: string, options?: Record<string, unknown>) => string;

export interface ReviewRow {
    /** The id the question renders under on its page (an item's question: its item-scoped id). */
    key: string;
    fieldId: string;
    title: string;
    /** What was answered, one line per value; none: unanswered. */
    lines: string[];
    /** A value the form set or locked: not the respondent's to change. */
    locked: 'filled' | 'read-only' | null;
    /** The page would not let them continue: a required answer is missing (`answer`) or an answer needs another look (`check`). */
    problem: 'answer' | 'check' | null;
}

export interface ReviewItem {
    key: string;
    header: string;
    rows: ReviewRow[];
}

export interface ReviewQuestion extends ReviewRow {
    /** A repeating group: its items, each with the questions answered in it. */
    items?: ReviewItem[];
}

export interface ReviewSection {
    /** The page's index in the form: where "Edit" goes. */
    slideIndex: number;
    /** The page's number, as "Page x of y" counts it. */
    number: number;
    /** The page's section title, if the form gave it one. */
    title: string;
    questions: ReviewQuestion[];
}

export interface ReviewInput {
    slides: StandardFormFieldDto[] | undefined;
    answers: Record<string, any>;
    /** The pages gone through, in order (`pathPages`). */
    path: number[];
    states: FieldRuleStates;
    hiddenValues?: Record<string, string>;
    language: 'en' | 'nl';
    t: Translate;
}

/** Fields that carry no answer: text blocks, images and videos, groups that do not repeat. */
const isContent = (field: StandardFormFieldDto): boolean => !field?.type || [FieldTypes.TEXT, FieldTypes.IMAGE_CONTENT, FieldTypes.VIDEO_CONTENT, FieldTypes.STATEMENT].includes(field.type) || (field.type === FieldTypes.GROUP && !isRepeatingGroup(field));

/** Questions the respondent was shown (not hidden by logic, not internal, not a kept-back calculation) and answers. */
const isReviewable = (field: StandardFormFieldDto, hidden: Set<string>): boolean => !hidden.has(field.id) && !field.internal && isShownToRespondents(field) && !isContent(field);

const present = (value: unknown): boolean => value !== undefined && value !== null && value !== '';

function dateText(value: string, language: 'en' | 'nl'): string {
    const date = isoToLocalDate(value);
    return date ? format(date, 'PPP', { locale: language === 'nl' ? dutch : undefined }) : value;
}

/** What an answer says, a line per value. Empty when nothing was answered. */
export function answerLines(field: StandardFormFieldDto, answers: Record<string, any>, language: 'en' | 'nl', t: Translate): string[] {
    const answer = answers?.[field.id];
    switch (field.type) {
        case FieldTypes.MULTIPLE_CHOICE:
        case FieldTypes.DROP_DOWN: {
            const text = choiceAnswerText(answer, field);
            return text === undefined ? [] : [text].flat();
        }
        case FieldTypes.YES_NO:
            return typeof answer?.boolean === 'boolean' ? [t(answer.boolean ? 'FIELD.YES' : 'FIELD.NO')] : [];
        case FieldTypes.RATING:
            return typeof answer?.number === 'number' ? [t('FIELD.RATED', { value: answer.number, total: field.properties?.steps || 5 })] : [];
        case FieldTypes.LINEAR_RATING:
            return typeof answer?.number === 'number' ? [String(answer.number)] : [];
        case FieldTypes.DATE: {
            const value = getComparableAnswerValue(answer, field.type);
            return present(value) ? [dateText(String(value), language)] : [];
        }
        case FieldTypes.FILE_UPLOAD:
        case FieldTypes.INPUT_FILE_UPLOAD: {
            // the file's name only: never its contents or link
            const file = answer?.file_metadata;
            return file ? [String(file.name ?? file.id ?? t('REVIEW.ANSWERED'))] : [];
        }
        case FieldTypes.TABULAR_INPUT: {
            const rowTitles: string[] = field.properties?.rowTitles ?? [];
            const values: string[][] = Array.isArray(answer?.tabular_value) ? answer.tabular_value : [];
            return values.flatMap((row, index) => {
                const cells = (row ?? []).filter(present).join(', ');
                // a row with nothing in it says nothing
                return cells ? [[rowTitles[index], cells].filter(present).join(': ')] : [];
            });
        }
        case FieldTypes.MATRIX: {
            const multiple = !!field.properties?.allowMultipleSelection;
            return (field.properties?.fields ?? [])
                .map((row, index) => {
                    const rowAnswer = answers?.[row.id];
                    const chosen = multiple ? (rowAnswer?.choices?.values ?? []) : rowAnswer?.choice?.value ? [rowAnswer.choice.value] : [];
                    const names = (row.properties?.choices ?? []).filter((choice: any) => chosen.includes(choice.id)).map((choice: any) => choice.value);
                    return names.length ? `${typeof row.title === 'string' && row.title ? row.title : `${index + 1}`}: ${names.join(', ')}` : '';
                })
                .filter(Boolean);
        }
        case FieldTypes.CALCULATED: {
            const value = calculatedAnswerValue(answer);
            if (value === null) return [];
            return [typeof value === 'boolean' ? t(value ? 'FIELD.CALCULATED_TRUE' : 'FIELD.CALCULATED_FALSE') : formatCalculatedValue(value, field.properties?.format, language)];
        }
        default: {
            const value = getComparableAnswerValue(answer, field.type);
            if (present(value) && !Array.isArray(value) && typeof value !== 'object') return [String(value)];
            // A kind of question this page does not know: say it was answered rather than leave it out.
            return hasAnswerValue(answer) ? [t('REVIEW.ANSWERED')] : [];
        }
    }
}

/** A question's title as plain text, as the respondent read it (pipes resolved, a rule's title in place of the form's). */
export function questionTitle(field: StandardFormFieldDto, pipe: PipeContext, states: FieldRuleStates, t: Translate): string {
    const ruleTitle = states.text(field.id)?.title;
    const legacy = legacyTitleText(field);
    const stringTitle = ruleTitle ? ruleTitle : typeof field.title === 'string' && field.title ? field.title : legacy;
    const title = stringTitle ? stringTitleToDoc(stringTitle) : field.title;
    const text = plainTextFromJson(resolvePipesInTitle(title, pipe)).replace(/\s+/g, ' ').trim();
    return text || t('REVIEW.UNTITLED');
}

/**
 * The review: the questions of every page on the respondent's path, as they
 * would be submitted. Read from the answers `normalizeGroupAnswersForSubmit`
 * gives over the visited path (what the submit sends), so a repeating group
 * the respondent never saw or a page they skipped is not listed. Questions hidden
 * by logic and internal ones are left out (hidden fields are not questions),
 * values a field rule set or locked are listed and marked. Pages with nothing
 * to review (text blocks only) are left out.
 */
export function reviewSections(input: ReviewInput): ReviewSection[] {
    const { slides, path, states, hiddenValues, language, t } = input;
    const sources = logicSourcesById(slides);
    const answers = normalizeGroupAnswersForSubmit(slides, input.answers ?? {}, path);
    const pipe: PipeContext = { slides, answers, hiddenValues, language };
    const itemLabelOf = (group: StandardFormFieldDto) => group.properties?.repeat?.itemLabel?.trim() || t('GROUP.ITEM');
    const sections: ReviewSection[] = [];

    path.forEach((slideIndex) => {
        const page = slides?.[slideIndex];
        if (!page) return;
        const fields = page.properties?.fields ?? [];
        const hidden = getHiddenFieldIds(fields, answers, sources);
        const invalid = pageInvalidations(page, slides, answers, states, sources);
        const problemOf = (key: string, lines: string[]): ReviewRow['problem'] => (invalid[key] ? (lines.length ? 'check' : 'answer') : null);
        const lockedOf = (field: StandardFormFieldDto): ReviewRow['locked'] => (states.isLocked(field.id) ? (states.valued.has(field.id) ? 'filled' : 'read-only') : null);

        const questions: ReviewQuestion[] = [];
        fields
            .filter((field) => isReviewable(field, hidden))
            .forEach((field) => {
                const row = (target: StandardFormFieldDto, scope: Record<string, any>, key: string, context: PipeContext): ReviewRow => {
                    const lines = answerLines(target, scope, language, t);
                    return { key, fieldId: target.id, title: questionTitle(target, context, states, t), lines, locked: key === target.id ? lockedOf(target) : null, problem: problemOf(key, lines) };
                };
                if (!isRepeatingGroup(field)) {
                    questions.push(row(field, answers, field.id, pipe));
                    return;
                }
                const items = getGroupItems(answers, field.id);
                const children = getGroupChildren(field);
                const lines: string[] = [];
                questions.push({
                    key: field.id,
                    fieldId: field.id,
                    title: questionTitle(field, pipe, states, t),
                    lines,
                    locked: null,
                    problem: invalid[field.id] ? 'check' : null,
                    items: items.map((item, index) => {
                        const scope = { groupId: field.id, index, childIds: children.map((child) => child.id) };
                        const context: PipeContext = { ...pipe, answers: itemScopeAnswers(answers, scope) };
                        const itemHidden = getItemHiddenChildIds(field, answers, index, sources);
                        return {
                            key: `${field.id}::${index}`,
                            header: getItemHeader(field, index, pipe, itemLabelOf(field)),
                            rows: children.filter((child) => isReviewable(child, itemHidden)).map((child) => row(child, item, scopedFieldId(child.id, index), context))
                        };
                    })
                });
            });
        if (questions.length) sections.push({ slideIndex, number: slideIndex + 1, title: page.properties?.sectionTitle?.trim() || '', questions });
    });
    return sections;
}

/** Does a row, or an item's row, still need the respondent? */
export const reviewProblems = (sections: ReviewSection[]): Array<{ slideIndex: number; row: ReviewRow }> =>
    sections.flatMap((section) =>
        section.questions
            .flatMap((question) => [question, ...(question.items ?? []).flatMap((item) => item.rows)])
            .filter((row) => row.problem)
            .map((row) => ({ slideIndex: section.slideIndex, row }))
    );

/** Where the form goes after the page at `slide`, with these answers: a page index, or `end` (submit). The same decision the page's Continue makes. */
export function nextPageAfter(slides: StandardFormFieldDto[] | undefined, slide: number, answers: Record<string, any>, sources: LogicSources = logicSourcesById(slides)): { target: number | 'end'; endingId?: string } {
    const page = slides?.[slide];
    const jump = resolveJump(page, answers, sources);
    if (jump?.target === JUMP_TARGET_SUBMIT) return { target: 'end', endingId: jump.endingId || undefined };
    if (jump?.target) {
        const index = slides?.findIndex((s) => s.id === jump.target) ?? -1;
        if (index >= 0) return { target: index };
    }
    return slide + 1 >= (slides?.length ?? 0) ? { target: 'end' } : { target: slide + 1 };
}

export type ReviewWalk =
    /** The pages after the edit still lead where they did: back to the review over `path`. */
    | { kind: 'review'; path: number[]; endingId?: string }
    /** An edit changed where the form goes at the page ending `path`: on from `target`, where the respondent fills in whatever is new. */
    | { kind: 'continue'; path: number[]; target: number }
    /** A page after the edit is not complete any more (an answer now required): the respondent goes to it. */
    | { kind: 'fix'; path: number[]; page: number };

/**
 * After an edit on `path[from]`: replay the rest of the path with the
 * answers as they are now. The page's own answers were checked by the caller.
 * While every page still has its answers and its jump leads to the next
 * page of the path, the respondent goes back to the review. Where a jump now
 * leads elsewhere they continue from there (the pages after it are no longer
 * on their path, and are dropped when they submit); a jump that now ends the
 * form shortens the path. Pages that became incomplete are visited first.
 */
export function walkReviewPath(input: { slides: StandardFormFieldDto[] | undefined; answers: Record<string, any>; path: number[]; from: number; states: FieldRuleStates }): ReviewWalk {
    const { slides, path, from, states } = input;
    const sources = logicSourcesById(slides);
    const answers = normalizeGroupAnswersForSubmit(slides, input.answers ?? {}, path);
    let endingId: string | undefined;
    for (let at = from; at < path.length; at++) {
        if (at > from && Object.keys(pageInvalidations(slides?.[path[at]], slides, answers, states, sources)).length) return { kind: 'fix', path: path.slice(0, at), page: path[at] };
        const next = nextPageAfter(slides, path[at], answers, sources);
        const last = at === path.length - 1;
        if (next.target === 'end') {
            endingId = next.endingId;
            return { kind: 'review', path: path.slice(0, at + 1), endingId };
        }
        if (last || next.target !== path[at + 1]) return { kind: 'continue', path: path.slice(0, at + 1), target: next.target };
    }
    return { kind: 'review', path, endingId };
}
