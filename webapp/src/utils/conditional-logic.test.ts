import { describe, expect, it } from 'vitest';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { Comparison, JUMP_TARGET_SUBMIT, LogicalOperator } from '@app/models/types/form-builder-shared';
import {
    areConditionsMet,
    computeFlowTraffic,
    evaluateConditions,
    flowTrafficFromPaths,
    fieldHasLogic,
    getComparableAnswerValue,
    getHiddenFieldIds,
    isFieldHiddenByLogic,
    isJumpTargetValid,
    logicSourcesById,
    pruneOrphanedConditions,
    resolveJumpTargetId,
    slideHasLogic,
    submissionPath
} from './conditional-logic';

/* ------------------------------ test helpers ----------------------------- */

const cond = (fieldId: string, comparison: Comparison, value: any = '', fieldType: string = FieldTypes.SHORT_TEXT) => ({ fieldId, fieldType, comparison, value });

const field = (id: string, type: string = FieldTypes.SHORT_TEXT, logic?: any): StandardFormFieldDto => ({ id, index: 0, type, properties: logic ? { logic } : {} });

const slide = (id: string, fields: StandardFormFieldDto[] = [], jumps?: any[]): StandardFormFieldDto =>
    ({ id, index: 0, type: FieldTypes.SLIDE, properties: { fields, ...(jumps ? { jumps } : {}) } }) as StandardFormFieldDto;

const textAnswer = (text: string) => ({ type: 'text', text });

/* --------------------------- getComparableAnswerValue -------------------- */

describe('getComparableAnswerValue', () => {
    it('maps each field type to its answer slot', () => {
        expect(getComparableAnswerValue({ text: 'hi' }, FieldTypes.SHORT_TEXT)).toBe('hi');
        expect(getComparableAnswerValue({ text: 'hi' }, FieldTypes.LONG_TEXT)).toBe('hi');
        expect(getComparableAnswerValue({ email: 'a@b.c' }, FieldTypes.EMAIL)).toBe('a@b.c');
        expect(getComparableAnswerValue({ url: 'https://x' }, FieldTypes.LINK)).toBe('https://x');
        expect(getComparableAnswerValue({ number: 7 }, FieldTypes.NUMBER)).toBe(7);
        expect(getComparableAnswerValue({ number: 3 }, FieldTypes.RATING)).toBe(3);
        expect(getComparableAnswerValue({ number: 9 }, FieldTypes.LINEAR_RATING)).toBe(9);
        expect(getComparableAnswerValue({ date: '2026-01-01' }, FieldTypes.DATE)).toBe('2026-01-01');
        expect(getComparableAnswerValue({ phoneNumber: '123' }, FieldTypes.PHONE_NUMBER)).toBe('123');
        expect(getComparableAnswerValue({ phone_number: '456' }, FieldTypes.PHONE_NUMBER)).toBe('456');
    });

    it('maps Yes/No booleans to the literal strings the builder offers', () => {
        expect(getComparableAnswerValue({ boolean: true }, FieldTypes.YES_NO)).toBe('Yes');
        expect(getComparableAnswerValue({ boolean: false }, FieldTypes.YES_NO)).toBe('No');
        expect(getComparableAnswerValue({}, FieldTypes.YES_NO)).toBeUndefined();
    });

    it('prefers multi-select values over single choice for choice fields', () => {
        expect(getComparableAnswerValue({ choice: { value: 'A' } }, FieldTypes.MULTIPLE_CHOICE)).toBe('A');
        expect(getComparableAnswerValue({ choices: { values: ['A', 'B'] } }, FieldTypes.MULTIPLE_CHOICE)).toEqual(['A', 'B']);
        expect(getComparableAnswerValue({ choice: { value: 'X' } }, FieldTypes.DROP_DOWN)).toBe('X');
    });

    it('returns undefined for a missing answer', () => {
        expect(getComparableAnswerValue(undefined, FieldTypes.SHORT_TEXT)).toBeUndefined();
        expect(getComparableAnswerValue(null, FieldTypes.NUMBER)).toBeUndefined();
    });
});

/* ------------------------------ comparisons ------------------------------ */

describe('evaluateConditions — comparison operators', () => {
    const answers = { q: textAnswer('Hello World') };
    const one = (comparison: Comparison, value: any, a: Record<string, any> = answers, fieldType: string = FieldTypes.SHORT_TEXT) =>
        evaluateConditions(LogicalOperator.AND, [cond('q', comparison, value, fieldType)], a);

    it('IS_EQUAL / IS_NOT_EQUAL compare as strings', () => {
        expect(one(Comparison.IS_EQUAL, 'Hello World')).toBe(true);
        expect(one(Comparison.IS_EQUAL, 'hello world')).toBe(false); // equality is case-sensitive
        expect(one(Comparison.IS_NOT_EQUAL, 'nope')).toBe(true);
        expect(one(Comparison.IS_NOT_EQUAL, 'Hello World')).toBe(false);
    });

    it('IS_EQUAL against a multi-select answer checks membership', () => {
        const a = { q: { choices: { values: ['Red', 'Blue'] } } };
        expect(one(Comparison.IS_EQUAL, 'Red', a, FieldTypes.MULTIPLE_CHOICE)).toBe(true);
        expect(one(Comparison.IS_EQUAL, 'Green', a, FieldTypes.MULTIPLE_CHOICE)).toBe(false);
        expect(one(Comparison.IS_NOT_EQUAL, 'Green', a, FieldTypes.MULTIPLE_CHOICE)).toBe(true);
    });

    it('CONTAINS / DOES_NOT_CONTAIN are case-insensitive on strings', () => {
        expect(one(Comparison.CONTAINS, 'hello')).toBe(true);
        expect(one(Comparison.CONTAINS, 'WORLD')).toBe(true);
        expect(one(Comparison.CONTAINS, 'xyz')).toBe(false);
        expect(one(Comparison.DOES_NOT_CONTAIN, 'xyz')).toBe(true);
    });

    it('CONTAINS on multi-select answers checks membership', () => {
        const a = { q: { choices: { values: ['Red', 'Blue'] } } };
        expect(one(Comparison.CONTAINS, 'Blue', a, FieldTypes.MULTIPLE_CHOICE)).toBe(true);
        expect(one(Comparison.DOES_NOT_CONTAIN, 'Green', a, FieldTypes.MULTIPLE_CHOICE)).toBe(true);
    });

    it('numeric comparisons', () => {
        const a = { q: { number: 10 } };
        expect(one(Comparison.GREATER_THAN, 5, a, FieldTypes.NUMBER)).toBe(true);
        expect(one(Comparison.GREATER_THAN, 10, a, FieldTypes.NUMBER)).toBe(false);
        expect(one(Comparison.GREATER_THAN_EQUAL, 10, a, FieldTypes.NUMBER)).toBe(true);
        expect(one(Comparison.LESS_THAN, 11, a, FieldTypes.NUMBER)).toBe(true);
        expect(one(Comparison.LESS_THAN_EQUAL, 9, a, FieldTypes.NUMBER)).toBe(false);
    });

    it('STARTS_WITH / ENDS_WITH are case-insensitive', () => {
        expect(one(Comparison.STARTS_WITH, 'hello')).toBe(true);
        expect(one(Comparison.ENDS_WITH, 'WORLD')).toBe(true);
        expect(one(Comparison.STARTS_WITH, 'World')).toBe(false);
    });

    it('IS_EMPTY / IS_NOT_EMPTY treat missing, empty string and empty array as empty', () => {
        expect(one(Comparison.IS_EMPTY, '', {})).toBe(true);
        expect(one(Comparison.IS_EMPTY, '', { q: textAnswer('') })).toBe(true);
        expect(one(Comparison.IS_EMPTY, '', { q: { choices: { values: [] } } }, FieldTypes.MULTIPLE_CHOICE)).toBe(true);
        expect(one(Comparison.IS_NOT_EMPTY, '', answers)).toBe(true);
        expect(one(Comparison.IS_NOT_EMPTY, '', {})).toBe(false);
    });
});

describe('evaluateConditions — folding', () => {
    const answers = { a: textAnswer('x'), b: textAnswer('y') };

    it('AND requires every condition', () => {
        expect(evaluateConditions(LogicalOperator.AND, [cond('a', Comparison.IS_EQUAL, 'x'), cond('b', Comparison.IS_EQUAL, 'y')], answers)).toBe(true);
        expect(evaluateConditions(LogicalOperator.AND, [cond('a', Comparison.IS_EQUAL, 'x'), cond('b', Comparison.IS_EQUAL, 'nope')], answers)).toBe(false);
    });

    it('OR requires any condition', () => {
        expect(evaluateConditions(LogicalOperator.OR, [cond('a', Comparison.IS_EQUAL, 'nope'), cond('b', Comparison.IS_EQUAL, 'y')], answers)).toBe(true);
        expect(evaluateConditions(LogicalOperator.OR, [cond('a', Comparison.IS_EQUAL, 'nope'), cond('b', Comparison.IS_EQUAL, 'nope')], answers)).toBe(false);
    });

    it('empty or incomplete condition sets never match', () => {
        expect(evaluateConditions(LogicalOperator.AND, [], answers)).toBe(false);
        expect(evaluateConditions(LogicalOperator.AND, undefined, answers)).toBe(false);
        // a condition without a fieldId is not evaluatable
        expect(evaluateConditions(LogicalOperator.AND, [cond('', Comparison.IS_EQUAL, 'x')], answers)).toBe(false);
    });
});

/* --------------------------- field visibility ---------------------------- */

describe('field visibility (SHOW / HIDE)', () => {
    const show = { action: 'SHOW', operator: LogicalOperator.AND, conditions: [cond('q', Comparison.IS_EQUAL, 'yes')] };
    const hide = { ...show, action: 'HIDE' };

    it('SHOW hides the field until conditions match', () => {
        expect(isFieldHiddenByLogic(field('f', FieldTypes.SHORT_TEXT, show), {})).toBe(true);
        expect(isFieldHiddenByLogic(field('f', FieldTypes.SHORT_TEXT, show), { q: textAnswer('yes') })).toBe(false);
    });

    it('HIDE shows the field until conditions match', () => {
        expect(isFieldHiddenByLogic(field('f', FieldTypes.SHORT_TEXT, hide), {})).toBe(false);
        expect(isFieldHiddenByLogic(field('f', FieldTypes.SHORT_TEXT, hide), { q: textAnswer('yes') })).toBe(true);
    });

    it('fields without a usable rule are always visible', () => {
        expect(isFieldHiddenByLogic(field('f'), {})).toBe(false);
        expect(isFieldHiddenByLogic(field('f', FieldTypes.SHORT_TEXT, { action: 'SHOW', operator: 'AND', conditions: [] }), {})).toBe(false);
    });

    it('getHiddenFieldIds collects only hidden fields', () => {
        const fields = [field('a', FieldTypes.SHORT_TEXT, show), field('b')];
        expect([...getHiddenFieldIds(fields, {})]).toEqual(['a']);
        expect([...getHiddenFieldIds(fields, { q: textAnswer('yes') })]).toEqual([]);
    });

    it('areConditionsMet mirrors evaluateConditions', () => {
        expect(areConditionsMet(show as any, { q: textAnswer('yes') })).toBe(true);
        expect(areConditionsMet(show as any, {})).toBe(false);
    });
});

/* ------------------------------- page jumps ------------------------------ */

describe('resolveJumpTargetId', () => {
    const s1 = slide('s1', [field('q')], [
        { operator: LogicalOperator.AND, conditions: [cond('q', Comparison.IS_EQUAL, 'a')], target: 's2' },
        { operator: LogicalOperator.AND, conditions: [cond('q', Comparison.IS_EQUAL, 'b')], target: JUMP_TARGET_SUBMIT }
    ]);

    it('returns null with no jumps or no match', () => {
        expect(resolveJumpTargetId(slide('x'), {})).toBeNull();
        expect(resolveJumpTargetId(s1, { q: textAnswer('zzz') })).toBeNull();
    });

    it('first matching rule wins, in order', () => {
        expect(resolveJumpTargetId(s1, { q: textAnswer('a') })).toBe('s2');
        expect(resolveJumpTargetId(s1, { q: textAnswer('b') })).toBe(JUMP_TARGET_SUBMIT);
        const both = slide('s', [], [
            { operator: LogicalOperator.AND, conditions: [cond('q', Comparison.IS_NOT_EMPTY)], target: 'first' },
            { operator: LogicalOperator.AND, conditions: [cond('q', Comparison.IS_NOT_EMPTY)], target: 'second' }
        ]);
        expect(resolveJumpTargetId(both, { q: textAnswer('x') })).toBe('first');
    });

    it('rules with empty conditions are skipped', () => {
        const s = slide('s', [], [{ operator: LogicalOperator.AND, conditions: [], target: 's2' }]);
        expect(resolveJumpTargetId(s, { q: textAnswer('a') })).toBeNull();
    });
});

describe('isJumpTargetValid', () => {
    const ids = new Set(['s1', 's2']);
    it('accepts existing slides and the submit sentinel', () => {
        expect(isJumpTargetValid('s1', ids)).toBe(true);
        expect(isJumpTargetValid(JUMP_TARGET_SUBMIT, ids)).toBe(true);
    });
    it('rejects deleted pages and empty targets', () => {
        expect(isJumpTargetValid('deleted', ids)).toBe(false);
        expect(isJumpTargetValid(undefined, ids)).toBe(false);
        expect(isJumpTargetValid('', ids)).toBe(false);
    });
});

/* ----------------------------- badge helpers ----------------------------- */

describe('fieldHasLogic / slideHasLogic', () => {
    const rule = { action: 'SHOW', operator: LogicalOperator.AND, conditions: [cond('q', Comparison.IS_NOT_EMPTY)] };

    it('detects field visibility rules', () => {
        expect(fieldHasLogic(field('f', FieldTypes.SHORT_TEXT, rule))).toBe(true);
        expect(fieldHasLogic(field('f'))).toBe(false);
        expect(fieldHasLogic(undefined)).toBe(false);
    });

    it('detects slide logic via jumps or field rules', () => {
        expect(slideHasLogic(slide('s', [], [{ operator: 'AND', conditions: [cond('q', Comparison.IS_EQUAL, 'x')], target: 't' }]))).toBe(true);
        expect(slideHasLogic(slide('s', [field('f', FieldTypes.SHORT_TEXT, rule)]))).toBe(true);
        expect(slideHasLogic(slide('s', [field('f')]))).toBe(false);
        // a jump with zero conditions is not usable logic
        expect(slideHasLogic(slide('s', [], [{ operator: 'AND', conditions: [], target: 't' }]))).toBe(false);
    });
});

/* --------------------------- orphaned-rule prune ------------------------- */

describe('pruneOrphanedConditions', () => {
    it('drops conditions pointing at deleted fields, and rules left empty', () => {
        const slides = [
            slide('s1', [field('alive')], [
                { operator: LogicalOperator.AND, conditions: [cond('alive', Comparison.IS_NOT_EMPTY), cond('ghost', Comparison.IS_EQUAL, 'x')], target: 's2' },
                { operator: LogicalOperator.AND, conditions: [cond('ghost', Comparison.IS_EQUAL, 'x')], target: 's2' }
            ]),
            slide('s2', [])
        ];
        pruneOrphanedConditions(slides);
        const jumps = slides[0].properties!.jumps as any[];
        expect(jumps).toHaveLength(1); // ghost-only rule removed entirely
        expect(jumps[0].conditions).toHaveLength(1);
        expect(jumps[0].conditions[0].fieldId).toBe('alive');
    });

    it('cleans field-visibility logic the same way', () => {
        const target = field('t', FieldTypes.SHORT_TEXT, { action: 'SHOW', operator: 'AND', conditions: [cond('ghost', Comparison.IS_EQUAL, 'x')] });
        const slides = [slide('s1', [target])];
        pruneOrphanedConditions(slides);
        expect(slides[0].properties!.fields![0].properties!.logic).toBeUndefined();
    });

    it('keeps jump targets pointing at deleted pages (surfaced as broken, not rewritten)', () => {
        const slides = [slide('s1', [field('q')], [{ operator: LogicalOperator.AND, conditions: [cond('q', Comparison.IS_NOT_EMPTY)], target: 'deleted-page' }])];
        pruneOrphanedConditions(slides);
        expect((slides[0].properties!.jumps as any[])[0].target).toBe('deleted-page');
    });
});

/* ------------------------------ flow traffic ----------------------------- */

describe('computeFlowTraffic', () => {
    const q = 'q1';
    const pages = [
        slide('p1', [field(q)], [{ operator: LogicalOperator.AND, conditions: [cond(q, Comparison.IS_EQUAL, 'skip')], target: JUMP_TARGET_SUBMIT }]),
        slide('p2', []),
        slide('p3', [])
    ];

    it('counts a purely linear response through every page', () => {
        const t = computeFlowTraffic(pages, [{ [q]: textAnswer('hello') }]);
        expect(t.total).toBe(1);
        expect(t.nodeVisits.get('p1')).toBe(1);
        expect(t.nodeVisits.get('p2')).toBe(1);
        expect(t.nodeVisits.get('p3')).toBe(1);
        expect(t.nextTraversals.get('__welcome__')).toBe(1);
        expect(t.nextTraversals.get('p1')).toBe(1);
        expect(t.jumpTraversals.size).toBe(0);
    });

    it('counts a jump-to-submit response only on the pages it saw', () => {
        const t = computeFlowTraffic(pages, [{ [q]: textAnswer('skip') }]);
        expect(t.nodeVisits.get('p1')).toBe(1);
        expect(t.nodeVisits.get('p2')).toBeUndefined();
        expect(t.jumpTraversals.get('p1:0')).toBe(1);
        expect(t.nextTraversals.get('p1')).toBeUndefined();
    });

    it('aggregates mixed traffic (the shipped verification scenario)', () => {
        const answers = [{ [q]: textAnswer('skip') }, { [q]: textAnswer('skip') }, { [q]: textAnswer('a') }, { [q]: textAnswer('b') }, { [q]: textAnswer('c') }, { [q]: textAnswer('d') }];
        const t = computeFlowTraffic(pages, answers);
        expect(t.total).toBe(6);
        expect(t.nodeVisits.get('p1')).toBe(6);
        expect(t.nodeVisits.get('p2')).toBe(4);
        expect(t.jumpTraversals.get('p1:0')).toBe(2);
        expect(t.nextTraversals.get('p1')).toBe(4);
    });

    it('jumps to a mid-form page resume the linear flow from there', () => {
        const withMidJump = [
            slide('a', [field(q)], [{ operator: LogicalOperator.AND, conditions: [cond(q, Comparison.IS_EQUAL, 'go')], target: 'c' }]),
            slide('b', []),
            slide('c', [])
        ];
        const t = computeFlowTraffic(withMidJump, [{ [q]: textAnswer('go') }]);
        expect(t.nodeVisits.get('a')).toBe(1);
        expect(t.nodeVisits.get('b')).toBeUndefined();
        expect(t.nodeVisits.get('c')).toBe(1);
        expect(t.jumpTraversals.get('a:0')).toBe(1);
    });

    it('broken jump targets fall back to the linear path', () => {
        const broken = [slide('a', [field(q)], [{ operator: LogicalOperator.AND, conditions: [cond(q, Comparison.IS_NOT_EMPTY)], target: 'deleted' }]), slide('b', [])];
        const t = computeFlowTraffic(broken, [{ [q]: textAnswer('x') }]);
        expect(t.nodeVisits.get('b')).toBe(1);
        expect(t.jumpTraversals.size).toBe(0);
    });

    it('terminates on cyclic rules (hop cap)', () => {
        const loop = [
            slide('a', [field(q)], [{ operator: LogicalOperator.AND, conditions: [cond(q, Comparison.IS_NOT_EMPTY)], target: 'b' }]),
            slide('b', [], [{ operator: LogicalOperator.AND, conditions: [cond(q, Comparison.IS_NOT_EMPTY)], target: 'a' }])
        ];
        const t = computeFlowTraffic(loop, [{ [q]: textAnswer('x') }]);
        const totalVisits = (t.nodeVisits.get('a') ?? 0) + (t.nodeVisits.get('b') ?? 0);
        expect(totalVisits).toBeGreaterThan(0);
        expect(totalVisits).toBeLessThanOrEqual(loop.length * 2 + 2); // capped, no infinite loop
    });

    it('handles zero submissions', () => {
        const t = computeFlowTraffic(pages, []);
        expect(t.total).toBe(0);
        expect(t.nodeVisits.size).toBe(0);
    });
});

/* --------------------------- submission paths ---------------------------- */

describe('submissionPath and flowTrafficFromPaths', () => {
    const q = 'q1';
    const pages = [
        slide('p1', [field(q)], [{ operator: LogicalOperator.AND, conditions: [cond(q, Comparison.IS_EQUAL, 'skip')], target: JUMP_TARGET_SUBMIT, endingId: 'early' }]),
        slide('p2', []),
        slide('p3', [])
    ];

    it('names the pages, the jumps taken and the ending (the server twin sends the same)', () => {
        expect(submissionPath(pages, { [q]: textAnswer('skip') })).toEqual({ steps: [{ pageId: 'p1', jump: 0 }], ended: true, endingId: 'early' });
        expect(submissionPath(pages, { [q]: textAnswer('go') })).toEqual({ steps: [{ pageId: 'p1' }, { pageId: 'p2' }, { pageId: 'p3' }], ended: true });
    });

    it('a looping path is not ended', () => {
        const loop = [
            slide('a', [field(q)], [{ operator: LogicalOperator.AND, conditions: [cond(q, Comparison.IS_NOT_EMPTY)], target: 'b' }]),
            slide('b', [], [{ operator: LogicalOperator.AND, conditions: [cond(q, Comparison.IS_NOT_EMPTY)], target: 'a' }])
        ];
        const path = submissionPath(loop, { [q]: textAnswer('x') });
        expect(path.ended).toBe(false);
        expect(path.steps).toHaveLength(loop.length * 2 + 2);
        expect(flowTrafficFromPaths([path]).endingVisits.size).toBe(0);
    });

    it('counts server paths (nulls left out) as replaying the answers would', () => {
        const answers = [{ [q]: textAnswer('skip') }, { [q]: textAnswer('a') }, { [q]: textAnswer('b') }];
        const fromServer = [
            { steps: [{ pageId: 'p1', jump: 0 }], ended: true, endingId: 'early' },
            { steps: [{ pageId: 'p1', jump: null }, { pageId: 'p2' }, { pageId: 'p3' }], ended: true, endingId: null },
            { steps: [{ pageId: 'p1' }, { pageId: 'p2' }, { pageId: 'p3' }], ended: true }
        ];
        expect(flowTrafficFromPaths(fromServer)).toEqual(computeFlowTraffic(pages, answers));
        const t = flowTrafficFromPaths(fromServer);
        expect(t.total).toBe(3);
        expect(t.endingVisits.get('early')).toBe(1);
        expect(t.endingVisits.get('')).toBe(2);
        expect(t.nextTraversals.get('__welcome__')).toBe(3);
        expect(t.nextTraversals.get('p3')).toBe(2);
    });
});

/* ---------------------------- choice questions --------------------------- */

describe('conditions on choice questions', () => {
    // As the builder makes them: options with an id and a text; answers hold
    // the chosen option's id, conditions the option's text (older and AI-made
    // rules) or its id.
    const choices = [
        { id: 'c-billing', value: 'Billing' },
        { id: 'c-tech', value: 'Technical issue' },
        { id: 'c-legacy', label: 'Legacy label' }
    ];
    const dropdown: StandardFormFieldDto = { id: 'topic', index: 0, type: FieldTypes.DROP_DOWN, properties: { choices } };
    const multi: StandardFormFieldDto = { id: 'tags', index: 0, type: FieldTypes.MULTIPLE_CHOICE, properties: { choices, allowMultipleSelection: true, allowOtherChoice: true } };
    const slides = [slide('p1', [dropdown, multi])];
    const sources = logicSourcesById(slides);
    const picked = (id: string) => ({ topic: { type: 'choice', choice: { value: id } } });
    const many = (values: string[], other?: string) => ({ tags: { type: 'choices', choices: { values, ...(other ? { other } : {}) } } });
    const on = (fieldId: string, fieldType: string, comparison: Comparison, value: any, answers: Record<string, any>, src = sources) =>
        evaluateConditions(LogicalOperator.AND, [cond(fieldId, comparison, value, fieldType)], answers, src);

    it('collects page questions and the questions of groups', () => {
        const group = { id: 'g', index: 0, type: FieldTypes.GROUP, properties: { repeat: {}, fields: [dropdown] } } as StandardFormFieldDto;
        expect(Object.keys(logicSourcesById([slide('p', [field('q'), group])])).sort()).toEqual(['g', 'q', 'topic']);
        expect(Object.keys(logicSourcesById(undefined))).toEqual([]);
    });

    it('matches the chosen option by its text, its id or its label', () => {
        expect(on('topic', FieldTypes.DROP_DOWN, Comparison.IS_EQUAL, 'Billing', picked('c-billing'))).toBe(true);
        expect(on('topic', FieldTypes.DROP_DOWN, Comparison.IS_EQUAL, 'c-billing', picked('c-billing'))).toBe(true);
        expect(on('topic', FieldTypes.DROP_DOWN, Comparison.IS_EQUAL, 'Legacy label', picked('c-legacy'))).toBe(true);
        expect(on('topic', FieldTypes.DROP_DOWN, Comparison.IS_EQUAL, 'Technical issue', picked('c-billing'))).toBe(false);
    });

    it('compares exactly and case-sensitively, as other equality does', () => {
        expect(on('topic', FieldTypes.DROP_DOWN, Comparison.IS_EQUAL, 'billing', picked('c-billing'))).toBe(false);
        expect(on('topic', FieldTypes.DROP_DOWN, Comparison.IS_EQUAL, 'Bill', picked('c-billing'))).toBe(false);
    });

    it('"is not" holds only when nothing the option answers to is equal', () => {
        expect(on('topic', FieldTypes.DROP_DOWN, Comparison.IS_NOT_EQUAL, 'Billing', picked('c-billing'))).toBe(false);
        expect(on('topic', FieldTypes.DROP_DOWN, Comparison.IS_NOT_EQUAL, 'c-billing', picked('c-billing'))).toBe(false);
        expect(on('topic', FieldTypes.DROP_DOWN, Comparison.IS_NOT_EQUAL, 'Billing', picked('c-tech'))).toBe(true);
        expect(on('topic', FieldTypes.DROP_DOWN, Comparison.IS_NOT_EQUAL, 'Billing', {})).toBe(true);
    });

    it('treats an unanswered choice as empty and a chosen one as not', () => {
        expect(on('topic', FieldTypes.DROP_DOWN, Comparison.IS_EMPTY, '', {})).toBe(true);
        expect(on('topic', FieldTypes.DROP_DOWN, Comparison.IS_EMPTY, '', picked('c-billing'))).toBe(false);
        expect(on('topic', FieldTypes.DROP_DOWN, Comparison.IS_NOT_EMPTY, '', picked('c-billing'))).toBe(true);
        expect(on('tags', FieldTypes.MULTIPLE_CHOICE, Comparison.IS_EMPTY, '', many([]))).toBe(true);
    });

    it('checks membership of several answers by text or id', () => {
        expect(on('tags', FieldTypes.MULTIPLE_CHOICE, Comparison.CONTAINS, 'Technical issue', many(['c-billing', 'c-tech']))).toBe(true);
        expect(on('tags', FieldTypes.MULTIPLE_CHOICE, Comparison.CONTAINS, 'c-tech', many(['c-tech']))).toBe(true);
        expect(on('tags', FieldTypes.MULTIPLE_CHOICE, Comparison.CONTAINS, 'Technical', many(['c-tech']))).toBe(false);
        expect(on('tags', FieldTypes.MULTIPLE_CHOICE, Comparison.DOES_NOT_CONTAIN, 'Billing', many(['c-tech']))).toBe(true);
        expect(on('tags', FieldTypes.MULTIPLE_CHOICE, Comparison.DOES_NOT_CONTAIN, 'Billing', many(['c-billing']))).toBe(false);
    });

    it('compares the text typed as "Other" as it is', () => {
        expect(on('tags', FieldTypes.MULTIPLE_CHOICE, Comparison.CONTAINS, 'Partners', many([], 'Partners'))).toBe(true);
        expect(on('tags', FieldTypes.MULTIPLE_CHOICE, Comparison.IS_NOT_EMPTY, '', many([], 'Partners'))).toBe(true);
        const other = { topic: { type: 'choice', choice: { other: 'Partners' } } };
        expect(on('topic', FieldTypes.DROP_DOWN, Comparison.IS_EQUAL, 'Partners', other)).toBe(true);
        expect(on('topic', FieldTypes.DROP_DOWN, Comparison.IS_NOT_EMPTY, '', other)).toBe(true);
    });

    it('matches only option ids when the form is not given', () => {
        const byId = cond('topic', Comparison.IS_EQUAL, 'c-billing', FieldTypes.DROP_DOWN);
        const byText = cond('topic', Comparison.IS_EQUAL, 'Billing', FieldTypes.DROP_DOWN);
        expect(evaluateConditions(LogicalOperator.AND, [byId], picked('c-billing'))).toBe(true);
        expect(evaluateConditions(LogicalOperator.AND, [byText], picked('c-billing'))).toBe(false);
    });

    it('shows, hides and jumps on an option text', () => {
        const shown = field('details', FieldTypes.SHORT_TEXT, { action: 'SHOW', operator: LogicalOperator.AND, conditions: [cond('topic', Comparison.IS_EQUAL, 'Billing', FieldTypes.DROP_DOWN)] });
        expect(isFieldHiddenByLogic(shown, picked('c-billing'), sources)).toBe(false);
        expect(isFieldHiddenByLogic(shown, picked('c-tech'), sources)).toBe(true);
        expect(getHiddenFieldIds([shown], picked('c-billing'), sources).size).toBe(0);
        const form = [slide('p1', [dropdown], [{ operator: LogicalOperator.AND, conditions: [cond('topic', Comparison.IS_EQUAL, 'Billing', FieldTypes.DROP_DOWN)], target: 'p3' }]), slide('p2'), slide('p3')];
        expect(resolveJumpTargetId(form[0], picked('c-billing'), logicSourcesById(form))).toBe('p3');
        expect(resolveJumpTargetId(form[0], picked('c-tech'), logicSourcesById(form))).toBeNull();
        // the flow view's insights read the options from the pages themselves
        expect(submissionPath(form, picked('c-billing')).steps.map((s) => s.pageId)).toEqual(['p1', 'p3']);
        expect(computeFlowTraffic(form, [picked('c-billing'), picked('c-tech')]).nodeVisits.get('p2')).toBe(1);
    });
});
