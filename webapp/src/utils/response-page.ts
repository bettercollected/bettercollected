import { FormTheme } from '@app/constants/theme';
import { FieldTypes, StandardFormDto, StandardFormFieldDto } from '@app/models/dtos/form';
import { logicSourcesById, submissionPath } from '@app/utils/conditional-logic';
import { getFormFields } from '@app/utils/form-builder-block-utils';
import { hasAnswerValue } from '@app/utils/repeating-groups';

export { responseOriginListUrl, responsePageUrl, responsesListUrl } from '@app/utils/response-urls';

const DEFAULT_THEME: Pick<FormTheme, 'primary' | 'secondary' | 'tertiary' | 'accent'> = { primary: '#101828', secondary: '#1649E2', tertiary: '#818CA0', accent: '#FFFFFF' };

/** The form's theme, with plain defaults for a form without one (an imported form). */
export function themeWithDefaults(theme?: Partial<FormTheme> | null): FormTheme {
    const own = (theme ?? {}) as Partial<FormTheme>;
    return {
        ...own,
        title: own.title ?? 'Default',
        primary: own.primary || DEFAULT_THEME.primary,
        secondary: own.secondary || DEFAULT_THEME.secondary,
        tertiary: own.tertiary || DEFAULT_THEME.tertiary,
        accent: own.accent || DEFAULT_THEME.accent
    };
}

export interface ResponsePageSection {
    page: StandardFormFieldDto;
    /** 1-based, among the form's pages. */
    number: number;
    /** False when the respondent's answers sent them past this page (a logic jump). */
    visited: boolean;
}

/**
 * The form's pages in order, each with whether this respondent went through
 * it. A form built in the builder has pages (`fields` are the pages); an
 * imported form has a flat list of questions, shown as one page.
 */
export function responsePageSections(form: StandardFormDto, answers: Record<string, any>): ResponsePageSection[] {
    if (form.builderVersion !== 'v2') {
        const fields = getFormFields(form);
        if (fields.length === 0) return [];
        const page = { id: 'page-1', index: 0, type: FieldTypes.SLIDE, properties: { fields } } as unknown as StandardFormFieldDto;
        return [{ page, number: 1, visited: true }];
    }
    const pages = (form.fields ?? []).filter((slide) => !slide.type || slide.type === FieldTypes.SLIDE);
    // Pages are only ever skipped by a page jump; replay it with the same rules the respondent ran.
    const hasJumps = pages.some((page) => ((page.properties?.jumps as unknown[] | undefined)?.length ?? 0) > 0);
    const visitedIds = hasJumps ? new Set(submissionPath(pages, answers, logicSourcesById(pages)).steps.map((step) => step.pageId)) : null;
    return pages.map((page, index) => ({ page, number: index + 1, visited: !visitedIds || visitedIds.has(page.id) }));
}

/** One row of a choice question: every option the form offers, with the ones chosen marked. */
export interface ChoiceRow {
    key: string;
    label: string;
    selected: boolean;
    /** The "Other" row: the respondent's own words. */
    other?: boolean;
}

/**
 * Every option of a choice question with the chosen ones marked. A stored
 * choice is the option's id; imported answers may carry its text instead. An
 * "Other" answer is its own row (marked, with the respondent's words); a form
 * that allows "Other" shows the row unmarked when it was not used.
 */
export function choiceRows(field: StandardFormFieldDto, answer: any, multiple: boolean): ChoiceRow[] {
    const chosen: string[] = multiple ? (Array.isArray(answer?.choices?.values) ? answer.choices.values : []) : answer?.choice?.value ? [String(answer.choice.value)] : [];
    const otherText: string = String((multiple ? answer?.choices?.other : answer?.choice?.other) ?? '').trim();
    const rows: ChoiceRow[] = (field.properties?.choices ?? []).map((choice, index) => ({
        key: choice.id ?? String(index),
        label: choice.value ? choice.value : `Item ${index + 1}`,
        selected: chosen.includes(String(choice.id)) || (!!choice.value && chosen.includes(choice.value))
    }));
    if (otherText) rows.push({ key: 'other', label: otherText, selected: true, other: true });
    else if (field.properties?.allowOtherChoice) rows.push({ key: 'other', label: 'Other', selected: false, other: true });
    return rows;
}

/** Whether an answer holds a value (0 and false count; an empty text does not). */
export function answered(answer: any): boolean {
    if (!answer || typeof answer !== 'object') return false;
    if (answer.items) return Array.isArray(answer.items) && answer.items.length > 0;
    return hasAnswerValue(answer);
}

/** Whether the response holds an answer to this question (a matrix answers row by row). */
export function fieldHasAnswer(field: StandardFormFieldDto, answers: Record<string, any>): boolean {
    if (field.type === FieldTypes.MATRIX) return (field.properties?.fields ?? []).some((row) => answered(answers[row.id]));
    return answered(answers[field.id]);
}

/** The language a form's dates and numbers are written in: the form's own (Dutch or English). */
export function formFormatLanguage(declared: string | null | undefined): 'en' | 'nl' {
    return (declared ?? '').trim().toLowerCase().split('-')[0] === 'nl' ? 'nl' : 'en';
}
