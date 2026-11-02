import { describe, expect, it } from 'vitest';

import { fieldRuleProblems } from '@app/lib/form-ops/field-rule-checks';
import type { FormDoc } from '@app/lib/form-ops/types';
import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { resolvePipesInText, stringTitleToDoc, titleHasPipes } from './answer-piping';
import { pipedInto } from './calculated-fields';
import { remapTextTokens } from './repeating-groups';

// The four places that read `{{field:key|fallback}}` out of plain text used to
// backtrack cubically on `{{field:` followed by a long run of spaces.
const SPACES = ' '.repeat(200_000);
const HOSTILE = `{{field:${SPACES}`;
const HOSTILE_CLOSED = `{{field:${SPACES}x`;
const FAST_MS = 200;

const timed = (run: () => unknown) => {
    const start = performance.now();
    run();
    return performance.now() - start;
};

const formWith = (text: string): FormDoc =>
    ({
        title: 'Pipes',
        builderVersion: 'v2',
        fields: [{ id: 'p1', index: 0, type: 'slide', properties: { fields: [{ id: 'q', index: 0, type: 'short_text', title: 'Question', properties: { rules: [{ id: 'r1', when: { expression: true }, then: { description: text } }] } }] } }]
    }) as unknown as FormDoc;

const pipedKeys = (text: string) => fieldRuleProblems(formWith(text)).map((problem) => /pipes '([^']*)'/.exec(problem.message)?.[1]);

describe('pipe patterns read in linear time', () => {
    it('the rule checker', () => {
        for (const text of [HOSTILE, HOSTILE_CLOSED, `${HOSTILE_CLOSED}}} {{field:${SPACES}|${SPACES}`]) expect(timed(() => fieldRuleProblems(formWith(text)))).toBeLessThan(FAST_MS);
    });

    it('answer piping', () => {
        const context = { answers: {}, slides: [], hiddenValues: {} } as any;
        for (const text of [HOSTILE, HOSTILE_CLOSED, `{{field:a|${SPACES}`]) {
            expect(timed(() => stringTitleToDoc(text))).toBeLessThan(FAST_MS);
            expect(timed(() => resolvePipesInText(text, context))).toBeLessThan(FAST_MS);
            expect(timed(() => titleHasPipes(text))).toBeLessThan(FAST_MS);
        }
    });

    it('repeating groups', () => {
        for (const text of [HOSTILE, HOSTILE_CLOSED, `{{field:a|${SPACES}`]) expect(timed(() => remapTextTokens(text, { a: 'b' }))).toBeLessThan(FAST_MS);
    });

    it('the calculation pipe notice', () => {
        const field = (id: string, title: string) => ({ id, index: 0, type: FieldTypes.SHORT_TEXT, title, properties: {} }) as unknown as StandardFormFieldDto;
        const slide = { id: 'p', index: 0, type: FieldTypes.SLIDE, properties: { fields: [field('risk', 'Risk'), field('note', `{{field:risk}} ${HOSTILE}`)] } } as unknown as StandardFormFieldDto;
        expect(timed(() => pipedInto([slide], 'risk'))).toBeLessThan(FAST_MS);
    });
});

describe('known tokens read as before', () => {
    const context = { answers: { 'name-field': { text: 'Ada' } }, slides: [{ id: 's', index: 0, type: FieldTypes.SLIDE, properties: { fields: [{ id: 'name-field', index: 0, type: FieldTypes.SHORT_TEXT }] } }], hiddenValues: { n: 'N-value' } } as any;

    it.each([
        ['{{ field : name-field | fb }}', 'Ada'],
        ['{{ field : abc | fb }}', 'fb'],
        ['{{field: g }}', ''],
        ['{{group:g:sum:c}}', ''],
        ['{{hidden:n|d}}', 'N-value'],
        ['{{hidden:other|d}}', 'd'],
        ['{{field:name-field}} and {{hidden:n}}', 'Ada and N-value'],
        ['{{field:a|x}} + {{field:b| y }}', 'x + y'],
        ['{{field:}}', '{{field:}}'],
        ['{{field:|fb}}', '{{field:|fb}}'],
        ['{{nothing:x}}', '{{nothing:x}}'],
        ['no tokens', 'no tokens']
    ])('renders %j as %j', (text, expected) => {
        expect(resolvePipesInText(text, context)).toBe(expected);
    });

    it.each([
        ['{{ field : abc | fb }}', true],
        ['{{field: g }}', true],
        ['{{group:g:sum:c}}', true],
        ['{{hidden:n|d}}', true],
        ['{{field:}}', false],
        ['{{nothing:x}}', false]
    ])('titleHasPipes(%j) is %j', (text, expected) => {
        expect(titleHasPipes(text)).toBe(expected);
    });

    it('turns text tokens into pipe nodes', () => {
        const nodes = stringTitleToDoc('Hi {{ field : abc | fb }}, {{field:}} and {{hidden:n|d}}!').content![0].content!;
        expect(nodes).toEqual([
            { type: 'text', text: 'Hi ' },
            { type: 'answerPipe', attrs: { kind: 'field', pipeKey: 'abc', label: 'abc', fallback: 'fb' } },
            { type: 'text', text: ', {{field:}} and ' },
            { type: 'answerPipe', attrs: { kind: 'hidden', pipeKey: 'n', label: 'n', fallback: 'd' } },
            { type: 'text', text: '!' }
        ]);
    });

    it.each([
        ['{{ field : abc | fb }}', '{{field:ABC| fb }}'],
        ['{{field: g }}', '{{field:g}}'],
        ['{{group:g:sum:c}}', '{{group:g:sum:C}}'],
        ['{{hidden:n|d}}', '{{hidden:n|d}}'],
        ['{{field:abc}} {{field:g|x}}', '{{field:ABC}} {{field:g|x}}'],
        ['{{field:}}', '{{field:}}'],
        ['{{nothing:x}}', '{{nothing:x}}']
    ])('remaps %j to %j', (text, expected) => {
        expect(remapTextTokens(text, { abc: 'ABC', c: 'C' })).toBe(expected);
    });

    it('names the key the rule checker reports', () => {
        expect(pipedKeys('{{ field : abc | fb }}')).toEqual(['abc']);
        expect(pipedKeys('{{field: g }}')).toEqual(['g']);
        expect(pipedKeys('{{group:g:sum:c}}')).toEqual(['g:sum:c']);
        expect(pipedKeys('{{hidden:n|d}}')).toEqual(['n']);
        expect(pipedKeys('{{field:abc}} then {{hidden:z}}')).toEqual(['abc', 'z']);
        expect(pipedKeys('{{field:}}')).toEqual(['']);
        expect(pipedKeys('{{nothing:x}}')).toEqual([]);
        expect(pipedKeys('{{field:q}}')).toEqual([]);
    });

    it('writes the label of a piped question in the calculation pipe notice', () => {
        const field = (id: string, title: string) => ({ id, index: 0, type: FieldTypes.SHORT_TEXT, title, properties: {} }) as unknown as StandardFormFieldDto;
        const slide = { id: 'p', index: 0, type: FieldTypes.SLIDE, properties: { fields: [field('risk', 'Risk'), field('note', 'Score {{ field : risk | ? }} and {{field:}}')] } } as unknown as StandardFormFieldDto;
        expect(pipedInto([slide], 'risk')).toEqual(['the title of question 2 on page 1 (“Score {Risk} and {{field:}}”)']);
    });
});
