import { describe, expect, it } from 'vitest';

import { FieldTypes, StandardFormDto, StandardFormFieldDto, StandardFormResponseDto } from '@app/models/dtos/form';
import { Comparison, LogicalOperator } from '@app/models/types/form-builder-shared';
import { groupPipeKey, pruneOrphanedPipes, resolvePipesInText, resolvePipeValue } from '@app/utils/answer-piping';
import { evaluateConditions, getHiddenFieldIds, pruneOrphanedConditions, resolveJumpTargetId } from '@app/utils/conditional-logic';
import { aggregateGroupNumbers, formatAggregate, joinList } from '@app/utils/group-aggregates';
import {
    addGroupItem,
    canAddItem,
    canRemoveItem,
    getDisplayedItemCount,
    getItemHeader,
    getItemHiddenChildIds,
    getRepeatSettings,
    itemScopeAnswers,
    normalizeGroupAnswersForSubmit,
    parseScopedFieldId,
    removeGroupItem,
    scopedFieldId,
    validateGroupAnswer,
    writeItemAnswers
} from '@app/utils/repeating-groups';
import { buildResponsesExport, formulaSafeCell, tableToCsv } from '@app/utils/response-export';
import { validateSlide } from '@app/utils/vvalidation-utils';

const name: StandardFormFieldDto = { id: 'name', index: 0, type: FieldTypes.SHORT_TEXT, title: 'Name', validations: { required: true } };
const income: StandardFormFieldDto = { id: 'income', index: 1, type: FieldTypes.NUMBER, title: 'Income' };
const guardian: StandardFormFieldDto = {
    id: 'guardian',
    index: 2,
    type: FieldTypes.SHORT_TEXT,
    title: 'Guardian',
    validations: { required: true },
    properties: { logic: { action: 'SHOW', operator: LogicalOperator.AND, conditions: [{ fieldId: 'income', fieldType: FieldTypes.NUMBER, comparison: Comparison.LESS_THAN, value: 10 }] } }
};

const group = (repeat: any = {}, children = [name, income]): StandardFormFieldDto => ({
    id: 'g',
    index: 1,
    type: FieldTypes.GROUP,
    title: 'Applicants',
    properties: { repeat: { minItems: 1, maxItems: 3, itemLabel: 'Applicant', ...repeat }, fields: children }
});

const intro: StandardFormFieldDto = { id: 'intro', index: 0, type: FieldTypes.SHORT_TEXT, title: 'Household' };
const slides = (g = group()): StandardFormFieldDto[] => [{ id: 's1', index: 0, type: FieldTypes.SLIDE, properties: { fields: [intro, g] } }];

const text = (t: string) => ({ type: 'text', text: t });
const num = (n: number) => ({ type: 'number', number: n });
const answersWith = (...items: Array<Record<string, any>>) => ({ g: { type: 'group', items } });

describe('repeat settings', () => {
    it('applies defaults, clamps limits and picks the export layout by size', () => {
        expect(getRepeatSettings(group({ minItems: 5, maxItems: 2 }))).toMatchObject({ minItems: 2, maxItems: 2, exportLayout: 'columns' });
        expect(getRepeatSettings(group({ maxItems: 8 })).exportLayout).toBe('rows');
        expect(getRepeatSettings(group({ maxItems: 8, exportLayout: 'columns' })).exportLayout).toBe('columns');
        expect(getRepeatSettings(group({ itemLabel: '' })).itemLabel).toBe('Item');
    });
});

describe('item scope', () => {
    it('layers the item over the form answers under child and scoped ids', () => {
        const answers = { intro: text('Sharma'), ...answersWith({ name: text('Sita') }, { name: text('Ram') }) };
        const view = itemScopeAnswers(answers, { groupId: 'g', index: 1, childIds: ['name', 'income'] });
        expect(view.name.text).toBe('Ram');
        expect(view[scopedFieldId('name', 1)].text).toBe('Ram');
        expect(view.intro.text).toBe('Sharma');
    });

    it('writes the scoped keys back into the right item, creating earlier items', () => {
        const next = writeItemAnswers({}, { groupId: 'g', index: 1, childIds: ['name'] }, { [scopedFieldId('name', 1)]: text('Ram'), name: text('ignored') });
        expect(next.g).toEqual({ type: 'group', items: [{}, { name: text('Ram') }] });
    });

    it('parses scoped ids', () => {
        expect(parseScopedFieldId('abc::2')).toEqual({ childId: 'abc', index: 2 });
        expect(parseScopedFieldId('abc')).toBeNull();
    });
});

describe('add / remove within limits', () => {
    const g = group({ minItems: 1, maxItems: 2 });

    it('shows at least the minimum and adds up to the maximum', () => {
        expect(getDisplayedItemCount(g, {})).toBe(1);
        const two = addGroupItem({}, g);
        expect(two.g.items).toHaveLength(2);
        expect(canAddItem(g, two)).toBe(false);
        expect(addGroupItem(two, g).g.items).toHaveLength(2);
    });

    it('removes only above the minimum', () => {
        expect(canRemoveItem(g, {})).toBe(false);
        const two = answersWith({ name: text('A') }, { name: text('B') });
        const one = removeGroupItem(two, g, 0);
        expect(one.g.items).toEqual([{ name: text('B') }]);
        expect(removeGroupItem(one, g, 0).g.items).toHaveLength(1);
    });

    it('drops a seen group that logic hid afterwards, or whose page is off the visited path', () => {
        const hiddenLater = group();
        hiddenLater.properties!.logic = { action: 'SHOW', operator: LogicalOperator.AND, conditions: [{ fieldId: 'intro', fieldType: FieldTypes.SHORT_TEXT, comparison: Comparison.IS_EQUAL, value: 'yes' }] };
        const stale = { intro: text('no'), g: { type: 'group', items: [{}] } };
        const submitted = normalizeGroupAnswersForSubmit(slides(hiddenLater), stale);
        expect(submitted.g).toBeUndefined();
        expect(submitted.intro).toEqual(text('no'));
        expect(normalizeGroupAnswersForSubmit(slides(hiddenLater), { ...stale, intro: text('yes') }).g.items).toHaveLength(1);

        const twoPages: StandardFormFieldDto[] = [
            { id: 's0', index: 0, type: FieldTypes.SLIDE, properties: { fields: [intro] } },
            { id: 's1', index: 1, type: FieldTypes.SLIDE, properties: { fields: [group()] } }
        ];
        const answers = { g: { type: 'group', items: [{ name: text('A') }] } };
        expect(normalizeGroupAnswersForSubmit(twoPages, answers, [-1, 0]).g).toBeUndefined();
        expect(normalizeGroupAnswersForSubmit(twoPages, answers, [-1, 0, 1]).g.items).toHaveLength(1);
    });

    it('treats null limits as unset and empty child answers as missing', () => {
        expect(getRepeatSettings(group({ minItems: null, maxItems: null }))).toMatchObject({ minItems: 1, maxItems: 3 });
        const invalid = validateGroupAnswer(group({ maxItems: 4 }), answersWith({ name: {} }, { name: { type: 'text', text: '' } }, { name: { choice: {} } }, { name: text('ok') }));
        expect(Object.keys(invalid)).toEqual([scopedFieldId('name', 0), scopedFieldId('name', 1), scopedFieldId('name', 2)]);
    });

    it('pads seen groups to the minimum on submit and leaves unseen groups absent', () => {
        const g2 = group({ minItems: 2 });
        expect(normalizeGroupAnswersForSubmit(slides(g2), { g: { type: 'group', items: [{ name: text('A') }] } }).g.items).toHaveLength(2);
        expect(normalizeGroupAnswersForSubmit(slides(g2), {}).g).toBeUndefined();
    });
});

describe('validation', () => {
    it('requires questions per item, keyed by scoped id', () => {
        const invalid = validateGroupAnswer(group(), answersWith({ name: text('A') }, { income: num(4) }));
        expect(Object.keys(invalid)).toEqual([scopedFieldId('name', 1)]);
    });

    it('does not require a question hidden by its item logic', () => {
        const g = group({}, [name, income, guardian]);
        const answers = answersWith({ name: text('A'), income: num(50) }, { name: text('B'), income: num(5) });
        expect(Object.keys(validateGroupAnswer(g, answers))).toEqual([scopedFieldId('guardian', 1)]);
        expect(getItemHiddenChildIds(g, answers, 0).has('guardian')).toBe(true);
        expect(getItemHiddenChildIds(g, answers, 1).has('guardian')).toBe(false);
    });

    it('flags too many stored items', () => {
        expect(validateGroupAnswer(group({ maxItems: 1 }), answersWith({ name: text('A') }, { name: text('B') })).g).toEqual(['MAX_ITEMS']);
    });

    it('page validation leaves groups to the group validator', () => {
        expect(validateSlide(slides()[0], {})).toEqual({});
    });
});

describe('conditional logic', () => {
    const answers = answersWith({ name: text('Sita'), income: num(30) }, { name: text('Ram'), income: num(5) });

    it('inside an item, siblings refer to the same item', () => {
        const scope = (index: number) => itemScopeAnswers(answers, { groupId: 'g', index, childIds: ['name', 'income', 'guardian'] });
        expect(getHiddenFieldIds([guardian], scope(0)).has('guardian')).toBe(true);
        expect(getHiddenFieldIds([guardian], scope(1)).has('guardian')).toBe(false);
    });

    it('outside, conditions work on the group as a whole', () => {
        const count = (comparison: Comparison, value: number) => evaluateConditions(LogicalOperator.AND, [{ fieldId: 'g', fieldType: 'group', groupMode: 'COUNT', comparison, value }], answers);
        expect(count(Comparison.IS_EQUAL, 2)).toBe(true);
        expect(count(Comparison.GREATER_THAN_EQUAL, 3)).toBe(false);
        expect(count(Comparison.LESS_THAN_EQUAL, 2)).toBe(true);

        const quantified = (groupMode: 'ANY' | 'ALL', value: number) =>
            evaluateConditions(LogicalOperator.AND, [{ fieldId: 'g', fieldType: 'group', groupMode, childFieldId: 'income', childFieldType: FieldTypes.NUMBER, comparison: Comparison.GREATER_THAN, value }], answers);
        expect(quantified('ANY', 20)).toBe(true);
        expect(quantified('ALL', 20)).toBe(false);
        expect(quantified('ALL', 1)).toBe(true);
        expect(evaluateConditions(LogicalOperator.AND, [{ fieldId: 'g', fieldType: 'group', groupMode: 'ALL', childFieldId: 'income', childFieldType: FieldTypes.NUMBER, comparison: Comparison.GREATER_THAN, value: 1 }], {})).toBe(false);
    });

    it('drives page jumps', () => {
        const slide = { ...slides()[0], properties: { ...slides()[0].properties, jumps: [{ operator: LogicalOperator.AND, target: '__SUBMIT__', conditions: [{ fieldId: 'g', fieldType: 'group', groupMode: 'COUNT' as const, comparison: Comparison.GREATER_THAN_EQUAL, value: 2 }] }] } };
        expect(resolveJumpTargetId(slide, answers)).toBe('__SUBMIT__');
    });

    it('prunes conditions on deleted group questions', () => {
        const target: StandardFormFieldDto = {
            id: 't',
            index: 2,
            type: FieldTypes.SHORT_TEXT,
            properties: { logic: { action: 'SHOW', operator: LogicalOperator.AND, conditions: [{ fieldId: 'g', fieldType: 'group', groupMode: 'ANY', childFieldId: 'gone', comparison: Comparison.IS_NOT_EMPTY, value: '' }] } }
        };
        const withGuardian = group({}, [name, income, { ...guardian, properties: { logic: { ...guardian.properties!.logic!, conditions: [{ fieldId: 'gone', fieldType: 'number', comparison: Comparison.IS_EMPTY, value: '' }] } } }]);
        const form: StandardFormFieldDto[] = [{ id: 's', index: 0, type: FieldTypes.SLIDE, properties: { fields: [withGuardian, target] } }];
        pruneOrphanedConditions(form);
        expect(target.properties?.logic).toBeUndefined();
        expect(withGuardian.properties?.fields?.[2].properties?.logic).toBeUndefined();
    });
});

describe('answer piping', () => {
    const answers = answersWith({ name: text('Sita Sharma'), income: num(1200) }, { name: text('Ram'), income: num(300.5) }, { name: text('Hari') });

    it('item header pipes the same item', () => {
        const g = group({ itemTitle: '{{field:name}}' });
        expect(getItemHeader(g, 0, { slides: slides(g), answers })).toBe('Applicant 1: Sita Sharma');
        expect(getItemHeader(g, 2, { slides: slides(g), answers })).toBe('Applicant 3: Hari');
        expect(getItemHeader(g, 3, { slides: slides(g), answers })).toBe('Applicant 4');
    });

    it('a sibling pipe inside an item resolves to that item', () => {
        const view = itemScopeAnswers(answers, { groupId: 'g', index: 1, childIds: ['name', 'income'] });
        expect(resolvePipeValue('field', 'name', { slides: slides(), answers: view })).toBe('Ram');
    });

    it('outside the group: count, joined list and aggregates', () => {
        const ctx = { slides: slides(), answers };
        expect(resolvePipesInText('You listed {{group:g:count}} applicants: {{group:g:list:name}}.', ctx)).toBe('You listed 3 applicants: Sita Sharma, Ram and Hari.');
        expect(resolvePipeValue('group', groupPipeKey('g', 'sum', 'income'), ctx)).toBe('1500.5');
        expect(resolvePipeValue('group', groupPipeKey('g', 'avg', 'income'), ctx)).toBe('750.25');
        expect(resolvePipeValue('group', groupPipeKey('g', 'min', 'income'), ctx)).toBe('300.5');
        expect(resolvePipeValue('group', groupPipeKey('g', 'max', 'income'), ctx)).toBe('1200');
        expect(resolvePipeValue('group', 'g:sum:missing', ctx)).toBeUndefined();
        expect(resolvePipesInText('{{group:g:max:income|none}}', { slides: slides(), answers: {} })).toBe('none');
    });

    it('prunes group pipes whose group or question is gone', () => {
        const pipe = (pipeKey: string) => ({ type: 'answerPipe', attrs: { kind: 'group', pipeKey } });
        const title = { type: 'doc', content: [{ type: 'paragraph', content: [pipe('g:count'), pipe('g:sum:income'), pipe('g:sum:gone'), pipe('nope:count')] }] };
        const form = slides();
        form[0].properties!.fields!.push({ id: 'summary', index: 2, type: FieldTypes.SHORT_TEXT, title: title as any });
        pruneOrphanedPipes(form);
        expect((title.content[0].content as any[]).map((n) => n.attrs.pipeKey)).toEqual(['g:count', 'g:sum:income']);
    });
});

describe('aggregates', () => {
    it('computes over answered numbers only', () => {
        const answer = { type: 'group', items: [{ income: num(2) }, {}, { income: num(4) }] };
        expect(aggregateGroupNumbers(answer, 'income', FieldTypes.NUMBER, 'sum')).toBe(6);
        expect(aggregateGroupNumbers(answer, 'income', FieldTypes.NUMBER, 'avg')).toBe(3);
        expect(aggregateGroupNumbers({ items: [] }, 'income', FieldTypes.NUMBER, 'avg')).toBeUndefined();
        expect(formatAggregate(1 / 3)).toBe('0.33');
    });

    it('joins lists naturally', () => {
        expect(joinList(['A'])).toBe('A');
        expect(joinList(['A', 'B'])).toBe('A and B');
        expect(joinList(['A', 'B', 'C'])).toBe('A, B and C');
        expect(joinList([])).toBeUndefined();
    });
});

describe('exports', () => {
    const form = (g: StandardFormFieldDto) => ({ formId: 'f', title: 'Loan', builderVersion: 'v2', fields: slides(g) }) as unknown as StandardFormDto;
    const responses = [
        { responseId: 'r1', dataOwnerIdentifier: 'a@x.org', answers: { intro: text('Sharma'), ...answersWith({ name: text('Sita'), income: num(10) }, { name: text('Ram') }) } },
        { responseId: 'r2', answers: { intro: text('Rai') } }
    ] as unknown as StandardFormResponseDto[];

    it('columns per item keep one row per submission', () => {
        const { main, groupTables } = buildResponsesExport(form(group({ maxItems: 2 })), responses);
        expect(main.headers).toEqual(['Responder ID', 'Household', 'Applicant 1 – Name', 'Applicant 1 – Income', 'Applicant 2 – Name', 'Applicant 2 – Income']);
        expect(main.rows).toEqual([
            ['a@x.org', 'Sharma', 'Sita', 10, 'Ram', ''],
            ['- -', 'Rai', '', '', '', '']
        ]);
        expect(groupTables).toEqual([]);
    });

    it('large groups get their own table keyed by response id and item number', () => {
        const { main, groupTables } = buildResponsesExport(form(group({ maxItems: 10 })), responses);
        expect(main.headers).toEqual(['Responder ID', 'Household', 'Applicants (Applicant count)', 'Response ID']);
        expect(main.rows[0]).toEqual(['a@x.org', 'Sharma', 2, 'r1']);
        expect(groupTables).toEqual([
            {
                name: 'Applicants',
                headers: ['Response ID', 'Applicant', 'Name', 'Income'],
                rows: [
                    ['r1', 1, 'Sita', 10],
                    ['r1', 2, 'Ram', '']
                ]
            }
        ]);
    });

    it('keeps internal (staff) columns after the respondent answers', () => {
        const staff: StandardFormFieldDto = { id: 'ref', index: 2, type: FieldTypes.SHORT_TEXT, title: 'Reference', internal: true };
        const withStaff = form(group({ maxItems: 10 }));
        withStaff.fields[0].properties!.fields!.push(staff);
        const staffResponses = [{ ...responses[0], internalAnswers: { ref: text('R-1') } }] as unknown as StandardFormResponseDto[];
        const { main } = buildResponsesExport(withStaff, staffResponses);
        expect(main.headers).toEqual(['Responder ID', 'Household', 'Applicants (Applicant count)', 'Internal: Reference', 'Response ID']);
        expect(main.rows[0]).toEqual(['a@x.org', 'Sharma', 2, 'R-1', 'r1']);
    });

    it('the creator can override the layout', () => {
        expect(buildResponsesExport(form(group({ maxItems: 2, exportLayout: 'rows' })), responses).groupTables).toHaveLength(1);
        expect(buildResponsesExport(form(group({ maxItems: 10, exportLayout: 'columns' })), responses).groupTables).toHaveLength(0);
    });

    it('neutralises formula-like text cells, leaving numbers and dates alone', () => {
        const csv = tableToCsv({ name: 't', headers: ['=HEADER'], rows: [['=HYPERLINK("x")', '+1', '-2', '@SUM(A1)', '\tx', '\rx', -5, 3, '2026-09-27', 'plain']] });
        const [, row] = csv.split('\r\n');
        expect(row).toBe(`"'=HYPERLINK(""x"")",'+1,'-2,'@SUM(A1),'\tx,"'\rx",-5,3,2026-09-27,plain`);
        expect(csv.startsWith("'=HEADER")).toBe(true);
        expect(formulaSafeCell(-5)).toBe(-5);
    });

    it('writes valid CSV', () => {
        expect(tableToCsv({ name: 't', headers: ['a', 'b'], rows: [['x, y', 'say "hi"']] })).toBe('a,b\r\n"x, y","say ""hi"""');
    });
});
