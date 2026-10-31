import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { dropOptionLogic } from '@app/utils/field-rule-copies';
import { OPTION_LOGIC_COST_PER_RESPONSE, checkOptionLogic, optionLogicProblems, optionLogicWarnings, pruneOptionLogic, worstCaseCost } from '@app/utils/option-logic';

const opts = (n: number, prefix = 'o') => Array.from({ length: n }, (_, i) => ({ id: `${prefix}${i}`, value: `${prefix} ${i}` }));
const slide = (fields: StandardFormFieldDto[]) => ({ id: 'p1', index: 0, type: FieldTypes.SLIDE, properties: { fields } }) as StandardFormFieldDto;
const q = (id: string, index: number, type: FieldTypes, properties: Record<string, unknown> = {}): StandardFormFieldDto => ({ id, index, type, title: id, properties }) as StandardFormFieldDto;
const cond = (fieldId: string, value = 'x', extra: Record<string, unknown> = {}) => ({ fieldId, fieldType: 'dropdown', comparison: 'IS_EQUAL', value, ...extra });
const show = (...conditions: unknown[]) => ({ action: 'SHOW', operator: 'AND', conditions }) as any;

describe('the structure checks of option logic', () => {
    it('counts each dropped piece once, as the server does', () => {
        const form = () => [
            slide([
                q('country', 0, FieldTypes.DROP_DOWN, { choices: opts(2, 'c') }),
                q('city', 1, FieldTypes.DROP_DOWN, {
                    choices: [
                        { id: 'a', value: 'A', logic: show(cond('country'), cond('gone')) },
                        { id: 'b', value: 'B' }
                    ]
                })
            ])
        ];
        expect(pruneOptionLogic(form())).toBe(1);
        const both = [
            slide([
                q('country', 0, FieldTypes.DROP_DOWN, { choices: opts(2, 'c') }),
                q('city', 1, FieldTypes.DROP_DOWN, {
                    choices: [
                        { id: 'a', value: 'A', logic: show(cond('gone'), cond('gone2')) },
                        { id: 'b', value: 'B' }
                    ]
                })
            ])
        ];
        expect(pruneOptionLogic(both)).toBe(2);
        expect(both[0].properties!.fields![1].properties!.choices![0].logic).toBeUndefined();
    });

    it('refuses a question with too many options instead of dropping its logic', () => {
        const many = opts(201);
        (many[0] as any).logic = show(cond('country'));
        const form = [slide([q('country', 0, FieldTypes.DROP_DOWN, { choices: opts(2, 'c') }), q('city', 1, FieldTypes.DROP_DOWN, { choices: many })])];
        const result = checkOptionLogic(form, true);
        expect(result.caps[0]).toContain('more than 200 options');
        expect(result.repaired).toBe(0);
        expect((form[0].properties!.fields![1].properties!.choices![0] as any).logic).toBeDefined();
        expect(optionLogicProblems(form).some((p) => p.message.includes('more than 200 options'))).toBe(true);
        expect(optionLogicWarnings(form).map((w) => w.code)).toEqual(['too_many_options']);
    });

    it('refuses a form whose worst case is over the budget, and not one within it', () => {
        const heavy = (options: number, conditions: number) => [
            slide([
                q('country', 0, FieldTypes.MULTIPLE_CHOICE, { allowMultipleSelection: true, choices: opts(options, 'c') }),
                q('pick', 1, FieldTypes.DROP_DOWN, { choices: opts(conditions, 'p').map((choice) => ({ ...choice, logic: show(...Array.from({ length: 20 }, () => cond('country', 'c 0', { fieldType: 'multiple_choice' }))) })) })
            ])
        ];
        expect(worstCaseCost(heavy(1000, 30))).toBeGreaterThan(OPTION_LOGIC_COST_PER_RESPONSE);
        expect(checkOptionLogic(heavy(1000, 30)).caps[0]).toContain('too costly to check');
        expect(checkOptionLogic(heavy(200, 5)).caps).toEqual([]);
    });

    it('leaves option logic out of a copy', () => {
        const copy = q('city', 1, FieldTypes.DROP_DOWN, {
            choices: [
                { id: 'a', value: 'A', logic: show(cond('country')) },
                { id: 'b', value: 'B' }
            ],
            optionFilter: { fieldId: 'country', mapping: [] }
        });
        dropOptionLogic(copy);
        expect(copy.properties!.optionFilter).toBeUndefined();
        expect('logic' in copy.properties!.choices![0]).toBe(false);
        expect(copy.properties!.choices).toHaveLength(2);
    });
});
