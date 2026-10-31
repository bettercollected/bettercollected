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
export function questionTitle(field: StandardFormFieldDto, pipe: PipeContext, states: FieldRuleStates, t: Translate, scope?: { groupId: string; index: number }): string {
    // a question inside a repeating-group item has its rule texts per item
    const ruleTitle = states.text(field.id, scope?.groupId, scope?.index)?.title;
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
 * by logic and internal ones are left out here (hidden fields are not
 * questions), values a field rule set or locked are listed and marked. Pages
 * with nothing to review (text blocks only) are left out.
 *
 * What the form no longer shows but still sends is not hidden from the
 * respondent: `alsoSentRows` lists it in a block of its own.
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
                const row = (target: StandardFormFieldDto, scope: Record<string, any>, key: string, context: PipeContext, inItem?: { groupId: string; index: number }): ReviewRow => {
                    const lines = answerLines(target, scope, language, t);
                    return { key, fieldId: target.id, title: questionTitle(target, context, states, t, inItem), lines, locked: key === target.id ? lockedOf(target) : null, problem: problemOf(key, lines) };
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
                            rows: children.filter((child) => isReviewable(child, itemHidden)).map((child) => row(child, item, scopedFieldId(child.id, index), context, { groupId: field.id, index }))
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

export interface AlsoSentRow {
    key: string;
    fieldId: string;
    title: string;
    lines: string[];
    /** The page the question is on, when known (1-based, as "Page x of y" counts). */
    page: number | null;
}

/**
 * What is sent although the review does not list it as a question: answers
 * the respondent gave earlier to questions their later answers now hide (the
 * form keeps and sends them), and uploaded files whose question is hidden or
 * on a page they skipped. Listing them keeps the review true to what is sent.
 * Questions hidden by logic are the plain ones on the visited pages, and the
 * questions of a group item hidden by an item rule; a repeating group that is
 * hidden is not sent at all, nor are the answers of skipped pages. Calculations
 * kept from respondents and internal questions are the form's, not answers.
 */
export function alsoSentRows(input: ReviewInput & { files?: ReadonlyArray<{ fieldId: string; fileName?: string }>; sections: ReviewSection[] }): AlsoSentRow[] {
    const { slides, path, states, hiddenValues, language, t } = input;
    const sources = logicSourcesById(slides);
    const answers = normalizeGroupAnswersForSubmit(slides, input.answers ?? {}, path);
    const pipe: PipeContext = { slides, answers, hiddenValues, language };
    const rows: AlsoSentRow[] = [];
    const listed = new Set(input.sections.flatMap((section) => section.questions.flatMap((question) => [question.fieldId, ...(question.items ?? []).flatMap((item) => item.rows.map((row) => row.fieldId))])));
    const isAnswer = (field: StandardFormFieldDto) => !field.internal && isShownToRespondents(field) && !isContent(field);

    path.forEach((slideIndex) => {
        const fields = slides?.[slideIndex]?.properties?.fields ?? [];
        const hidden = getHiddenFieldIds(fields, answers, sources);
        fields.forEach((field) => {
            if (isRepeatingGroup(field)) {
                if (hidden.has(field.id)) return;
                const children = getGroupChildren(field);
                getGroupItems(answers, field.id).forEach((item, index) => {
                    const itemHidden = getItemHiddenChildIds(field, answers, index, sources);
                    const scope = { groupId: field.id, index, childIds: children.map((child) => child.id) };
                    children
                        .filter((child) => itemHidden.has(child.id) && isAnswer(child))
                        .forEach((child) => {
                            const lines = answerLines(child, item, language, t);
                            if (lines.length)
                                rows.push({
                                    key: `${field.id}::${index}::${child.id}`,
                                    fieldId: child.id,
                                    title: `${getItemHeader(field, index, pipe, field.properties?.repeat?.itemLabel?.trim() || t('GROUP.ITEM'))}: ${questionTitle(child, { ...pipe, answers: itemScopeAnswers(answers, scope) }, states, t, { groupId: field.id, index })}`,
                                    lines,
                                    page: slideIndex + 1
                                });
                        });
                });
                return;
            }
            if (!hidden.has(field.id) || !isAnswer(field)) return;
            const lines = answerLines(field, answers, language, t);
            if (lines.length) rows.push({ key: field.id, fieldId: field.id, title: questionTitle(field, pipe, states, t), lines, page: slideIndex + 1 });
        });
    });

    // Files are sent whatever their page: one whose question the review does not list is named here.
    const byId = new Map<string, { field: StandardFormFieldDto; page: number }>();
    (slides ?? []).forEach((slide, index) => (slide?.properties?.fields ?? []).forEach((field) => byId.set(field.id, { field, page: index + 1 })));
    (input.files ?? []).forEach((file, index) => {
        if (listed.has(file.fieldId) || rows.some((row) => row.fieldId === file.fieldId)) return;
        const known = byId.get(file.fieldId);
        rows.push({ key: `file-${file.fieldId}-${index}`, fieldId: file.fieldId, title: known ? questionTitle(known.field, pipe, states, t) : t('REVIEW.UPLOADED_FILE'), lines: [file.fileName || t('REVIEW.ANSWERED')], page: known?.page ?? null });
    });
    return rows;
}

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
    /** The pages still lead where they did: back to the review over `path`. */
    | { kind: 'review'; path: number[]; endingId?: string }
    /** An edit sends the form to a page the respondent has not been through: on from `target`, where they fill in whatever is new. */
    | { kind: 'continue'; path: number[]; target: number }
    /** A page on the way is not complete any more (an answer now required): the respondent goes to it. */
    | { kind: 'fix'; path: number[]; page: number };

/**
 * After an edit: replay the whole reviewed path from its first page with the
 * answers as they are now, following the jumps as the form does (not from
 * the edited page: a change there can alter where an earlier page of the path
 * leads too, and the respondent may have moved on with Continue before coming
 * back). While every page on the way is complete and one the respondent has
 * been through, they go back to the review over the route as it now runs: a
 * page the route skips drops off the path (and its answers are not sent), a
 * jump that now ends the form shortens it. A route that reaches a page they
 * never saw continues there; a page that became incomplete is visited first.
 * Every page on the route, the edited one too, must be complete.
 */
export function walkReviewPath(input: { slides: StandardFormFieldDto[] | undefined; answers: Record<string, any>; path: number[]; states: FieldRuleStates }): ReviewWalk {
    const { slides, path, states } = input;
    const sources = logicSourcesById(slides);
    const answers = normalizeGroupAnswersForSubmit(slides, input.answers ?? {}, path);
    const reviewed = new Set(path);
    const route: number[] = [];
    let page = path[0];
    for (let hops = 0; hops <= (slides?.length ?? 0) * 2 + 2 && page !== undefined; hops++) {
        // a page twice on the route (rules that loop) is not one the review can list: the respondent carries on from it
        if (route.includes(page)) return { kind: 'continue', path: route, target: page };
        if (Object.keys(pageInvalidations(slides?.[page], slides, answers, states, sources)).length) return { kind: 'fix', path: [...route], page };
        route.push(page);
        const next = nextPageAfter(slides, page, answers, sources);
        if (next.target === 'end') return { kind: 'review', path: route, endingId: next.endingId };
        if (!reviewed.has(next.target)) return { kind: 'continue', path: route, target: next.target };
        page = next.target;
    }
    return { kind: 'review', path: route };
}
