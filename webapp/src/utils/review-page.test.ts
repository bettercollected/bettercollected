import { describe, expect, it } from 'vitest';

import { NO_RULES } from '@app/lib/field-rules';
import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { JUMP_TARGET_SUBMIT, LogicalOperator } from '@app/models/types/form-builder-shared';

import { progressPercent } from './form-progress';
import { REVIEW_SLIDE, answerLines, isReviewEnabled, nextPageAfter, pathPages, reviewProblems, reviewSections, walkReviewPath } from './review-page';

// the strings the page would show (the respondent locale's English, abridged)
const STRINGS: Record<string, string> = {
    'FIELD.YES': 'Yes',
    'FIELD.NO': 'No',
    'FIELD.RATED': '{{value}} of {{total}}',
    'REVIEW.ANSWERED': 'Answered',
    'REVIEW.UNTITLED': 'Untitled question',
    'GROUP.ITEM': 'Item',
    'FIELD.CALCULATED_TRUE': 'Yes',
    'FIELD.CALCULATED_FALSE': 'No'
};
const t = (key: string, options?: Record<string, unknown>) => (STRINGS[key] ?? key).replace(/\{\{(\w+)\}\}/g, (_, name) => String(options?.[name]));

const q = (id: string, type: FieldTypes | string, title: string, extra: Partial<StandardFormFieldDto> = {}, properties: StandardFormFieldDto['properties'] = {}): StandardFormFieldDto => ({
    id,
    index: 0,
    type: type as FieldTypes,
    title,
    properties: { fields: [], ...properties },
    validations: { required: false },
    ...extra
});
const page = (id: string, index: number, fields: StandardFormFieldDto[], properties: StandardFormFieldDto['properties'] = {}): StandardFormFieldDto => ({ id, index, type: FieldTypes.SLIDE, properties: { fields, ...properties } });
const text = (value: string) => ({ type: 'text', text: value });
const when = (fieldId: string, value: string) => ({ operator: LogicalOperator.AND, conditions: [{ fieldId, fieldType: 'short_text', comparison: 'IS_EQUAL', value }] });

describe('isReviewEnabled', () => {
    it('is off unless the form asks, and for a form without pages or one that takes no responses', () => {
        const fields = [page('p', 0, [])];
        expect(isReviewEnabled({ settings: { showReviewPage: true } as any, fields })).toBe(true);
        expect(isReviewEnabled({ settings: {} as any, fields })).toBe(false);
        expect(isReviewEnabled({ fields })).toBe(false);
        expect(isReviewEnabled({ settings: { showReviewPage: true } as any, fields: [] })).toBe(false);
        expect(isReviewEnabled({ settings: { showReviewPage: true } as any, fields, unavailable: 'closed' as any })).toBe(false);
        expect(isReviewEnabled(undefined)).toBe(false);
    });
});

describe('pathPages', () => {
    it('keeps the pages, in order, once each, without the welcome page or the review', () => {
        expect(pathPages([-1, 0, 2, 0, REVIEW_SLIDE, 3])).toEqual([0, 2, 3]);
        expect(pathPages(undefined)).toEqual([]);
    });
});

describe('progress on the review page', () => {
    it('is full: every page is answered', () => {
        expect(progressPercent([page('a', 0, []), page('b', 1, [])], REVIEW_SLIDE, {})).toBe(100);
    });
});

describe('answerLines', () => {
    const choice = q(
        'c',
        FieldTypes.MULTIPLE_CHOICE,
        'Pick',
        {},
        {
            choices: [
                { id: 'x', value: 'Apple' },
                { id: 'y', value: 'Pear' },
                { id: 'z', value: '' }
            ] as any
        }
    );
    it('says what was answered in the respondent words, a line per value', () => {
        expect(answerLines(choice, { c: { type: 'choice', choice: { value: 'y' } } }, 'en', t)).toEqual(['Pear']);
        expect(answerLines({ ...choice, properties: { ...choice.properties, allowMultipleSelection: true } }, { c: { type: 'choices', choices: { values: ['x', 'z'], other: 'Plum' } } }, 'en', t)).toEqual(['Apple', 'Item 3', 'Plum']);
        expect(answerLines(q('yn', FieldTypes.YES_NO, 'Agree'), { yn: { type: 'boolean', boolean: false } }, 'en', t)).toEqual(['No']);
        expect(answerLines(q('r', FieldTypes.RATING, 'Rate', {}, { steps: 7 }), { r: { type: 'rating', number: 4 } }, 'en', t)).toEqual(['4 of 7']);
        expect(answerLines(q('n', FieldTypes.NUMBER, 'How many'), { n: { type: 'number', number: 0 } }, 'en', t)).toEqual(['0']);
    });

    it('writes a date in the respondent language', () => {
        const date = q('d', FieldTypes.DATE, 'When');
        expect(answerLines(date, { d: { type: 'date', date: '2026-10-30' } }, 'en', t)).toEqual(['October 30th, 2026']);
        expect(answerLines(date, { d: { type: 'date', date: '2026-10-30' } }, 'nl', t)).toEqual(['30 oktober 2026']);
    });

    it('names a file, a table and a matrix, a row each', () => {
        expect(answerLines(q('f', FieldTypes.FILE_UPLOAD, 'CV'), { f: { type: 'file_upload', file_metadata: { id: 'i', name: 'cv.pdf', url: 'https://x/secret' } } }, 'en', t)).toEqual(['cv.pdf']);
        expect(
            answerLines(
                q('tb', FieldTypes.TABULAR_INPUT, 'Costs', {}, { rowTitles: ['Travel', 'Food'] }),
                {
                    tb: {
                        type: 'tabular_input',
                        tabular_value: [
                            ['10', 'bus'],
                            ['', '']
                        ]
                    }
                },
                'en',
                t
            )
        ).toEqual(['Travel: 10, bus']);
        const matrix = q(
            'm',
            FieldTypes.MATRIX,
            'Rate',
            {},
            {
                fields: [
                    q(
                        'r1',
                        FieldTypes.MATRIX_ROW_INPUT,
                        'Quality',
                        {},
                        {
                            choices: [
                                { id: 'p', value: 'Poor' },
                                { id: 'g', value: 'Great' }
                            ] as any
                        }
                    ),
                    q(
                        'r2',
                        FieldTypes.MATRIX_ROW_INPUT,
                        'Speed',
                        {},
                        {
                            choices: [
                                { id: 'p', value: 'Poor' },
                                { id: 'g', value: 'Great' }
                            ] as any
                        }
                    )
                ]
            }
        );
        expect(answerLines(matrix, { r1: { type: 'choice', choice: { value: 'g' } } }, 'en', t)).toEqual(['Quality: Great']);
    });

    it('is empty when nothing was answered, and never silent about a kind it does not know', () => {
        expect(answerLines(q('s', FieldTypes.SHORT_TEXT, 'Name'), {}, 'en', t)).toEqual([]);
        expect(answerLines(q('s', FieldTypes.SHORT_TEXT, 'Name'), { s: text('') }, 'en', t)).toEqual([]);
        expect(answerLines(q('new', 'a_future_question', 'New'), { new: { type: 'a_future_question', blob: { a: 1 } } }, 'en', t)).toEqual(['Answered']);
        expect(answerLines(q('new', 'a_future_question', 'New'), {}, 'en', t)).toEqual([]);
    });
});

describe('reviewSections', () => {
    const slides = [
        page(
            's1',
            0,
            [
                q('a', FieldTypes.SHORT_TEXT, 'First'),
                q('b', FieldTypes.SHORT_TEXT, 'Only if x', {}, { logic: { action: 'SHOW', ...when('a', 'x') } as any }),
                q('i', FieldTypes.SHORT_TEXT, 'Internal', { internal: true }),
                q('txt', FieldTypes.TEXT, 'Just text')
            ],
            { jumps: [{ ...when('a', 'skip'), target: 's3' }] }
        ),
        page('s2', 1, [q('c', FieldTypes.SHORT_TEXT, 'Second')]),
        page('s3', 2, [q('d', FieldTypes.SHORT_TEXT, 'Third', { validations: { required: true } })], { sectionTitle: 'Last bit' }),
        page('s4', 3, [q('only-text', FieldTypes.TEXT, 'Nothing to answer')])
    ];
    const input = (answers: Record<string, any>, path: number[]) => ({ slides, answers, path, states: NO_RULES, language: 'en' as const, t });
    const titles = (sections: ReturnType<typeof reviewSections>) => sections.flatMap((s) => s.questions.map((qn) => qn.title));

    it('lists the questions of the pages on the path, not hidden or internal ones, and no page of text alone', () => {
        const sections = reviewSections(input({ a: text('hello'), b: text('hidden'), i: text('staff'), c: text('two'), d: text('three') }, [0, 1, 2, 3]));
        expect(titles(sections)).toEqual(['First', 'Second', 'Third']);
        expect(sections.map((s) => [s.slideIndex, s.number, s.title])).toEqual([
            [0, 1, ''],
            [1, 2, ''],
            [2, 3, 'Last bit']
        ]);
    });

    it('shows a conditional question once its condition holds', () => {
        expect(titles(reviewSections(input({ a: text('x'), b: text('shown') }, [0])))).toEqual(['First', 'Only if x']);
    });

    it('leaves out a page the path skipped, though its answer is still in the browser', () => {
        const sections = reviewSections(input({ a: text('skip'), c: text('stale'), d: text('three') }, [0, 2]));
        expect(titles(sections)).toEqual(['First', 'Third']);
    });

    it('flags a required question that is empty and one that needs another look', () => {
        const sections = reviewSections(input({ a: text('hello') }, [0, 2]));
        expect(reviewProblems(sections).map(({ slideIndex, row }) => [slideIndex, row.title, row.problem])).toEqual([[2, 'Third', 'answer']]);
    });
});

describe('nextPageAfter and walkReviewPath', () => {
    const slides = [
        page('s1', 0, [q('a', FieldTypes.SHORT_TEXT, 'A')], {
            jumps: [
                { ...when('a', 'skip'), target: 's3' },
                { ...when('a', 'stop'), target: JUMP_TARGET_SUBMIT, endingId: 'bye' }
            ]
        }),
        page('s2', 1, [q('b', FieldTypes.SHORT_TEXT, 'B')]),
        page('s3', 2, [q('c', FieldTypes.SHORT_TEXT, 'C', { validations: { required: true } })])
    ];
    const answers = (a: string, c?: string) => ({ a: text(a), b: text('b'), ...(c ? { c: text(c) } : {}) });

    it('decides like the page does: a jump, the end, or the next page', () => {
        expect(nextPageAfter(slides, 0, answers('skip'))).toEqual({ target: 2 });
        expect(nextPageAfter(slides, 0, answers('stop'))).toEqual({ target: 'end', endingId: 'bye' });
        expect(nextPageAfter(slides, 0, answers('go'))).toEqual({ target: 1 });
        expect(nextPageAfter(slides, 2, answers('go'))).toEqual({ target: 'end' });
    });

    it('goes back to the review while the pages still lead where they did', () => {
        expect(walkReviewPath({ slides, answers: answers('go', 'c'), path: [0, 1, 2], states: NO_RULES })).toEqual({ kind: 'review', path: [0, 1, 2], endingId: undefined });
    });

    it('replays from the first page: a route that skips a reviewed page drops it, one that reaches an unseen page continues there', () => {
        // page 1 now jumps to page 3, which was reviewed: the review over the shorter route
        expect(walkReviewPath({ slides, answers: answers('skip', 'c'), path: [0, 1, 2], states: NO_RULES })).toEqual({ kind: 'review', path: [0, 2], endingId: undefined });
        // the same when the respondent went on to page 3 meanwhile: nothing depends on where the edit was
        expect(walkReviewPath({ slides, answers: answers('skip', 'c'), path: [0, 2], states: NO_RULES })).toEqual({ kind: 'review', path: [0, 2], endingId: undefined });
        // a route to a page the reviewed path never had
        expect(walkReviewPath({ slides, answers: answers('go', 'c'), path: [0, 2], states: NO_RULES })).toEqual({ kind: 'continue', path: [0], target: 1 });
    });

    it('shortens the path when the edit makes a page end the form, with that ending', () => {
        expect(walkReviewPath({ slides, answers: answers('stop', 'c'), path: [0, 1, 2], states: NO_RULES })).toEqual({ kind: 'review', path: [0], endingId: 'bye' });
    });

    it('goes to a later page that is not complete any more', () => {
        expect(walkReviewPath({ slides, answers: answers('go'), path: [0, 1, 2], states: NO_RULES })).toEqual({ kind: 'fix', path: [0, 1], page: 2 });
    });
});
