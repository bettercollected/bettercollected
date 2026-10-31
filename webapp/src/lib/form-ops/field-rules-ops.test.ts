import { describe, expect, it } from 'vitest';

import { idMaker } from './__fixtures__/forms';
import { applyOps } from './apply';
import { fieldRuleFixes, fieldRuleProblems } from './field-rule-checks';
import { locateField } from './model';
import type { FormDoc, FormOp } from './types';

const NL = { id: 'r_nl', when: { conditions: [{ fieldId: 'q_country', comparison: 'IS_EQUAL', value: 'Netherlands' }] }, then: { required: true } };

function base(): FormDoc {
    return {
        title: 'Rules',
        builderVersion: 'v2',
        fields: [
            {
                id: 'p1',
                index: 0,
                type: 'slide',
                properties: {
                    fields: [
                        {
                            id: 'q_country',
                            index: 0,
                            type: 'dropdown',
                            title: 'Country',
                            properties: {
                                choices: [
                                    { id: 'c_nl', value: 'Netherlands' },
                                    { id: 'c_be', value: 'Belgium' }
                                ]
                            }
                        },
                        { id: 'q_postcode', index: 1, type: 'short_text', title: 'Postcode' },
                        { id: 'q_qty', index: 2, type: 'number', title: 'Quantity' },
                        { id: 'q_total', index: 3, type: 'number', title: 'Total' },
                        {
                            id: 'q_pick',
                            index: 4,
                            type: 'dropdown',
                            title: 'Pick',
                            properties: {
                                choices: [
                                    { id: 'c_a', value: 'A' },
                                    { id: 'c_b', value: 'B' }
                                ]
                            }
                        }
                    ]
                }
            },
            { id: 'p2', index: 1, type: 'slide', properties: { fields: [{ id: 'q_note', index: 0, type: 'short_text', title: 'Note' }] } }
        ]
    } as unknown as FormDoc;
}

const run = (ops: any[], doc: FormDoc = base(), atomic = true) => applyOps(doc, ops as FormOp[], { atomic, newId: idMaker() });
const rulesOf = (doc: FormDoc, id: string) => locateField(doc, id).field.properties?.rules as any[] | undefined;
const withRules = (): FormDoc => run([{ op: 'set_field_rules', fieldId: 'q_postcode', rules: [NL] }]).doc;
const thawed = (doc: FormDoc): FormDoc => JSON.parse(JSON.stringify(doc));

describe('set_field_rules', () => {
    it('stores the resolved rule and says how many it set', () => {
        const { doc, results } = run([{ op: 'set_field_rules', fieldId: 'q_postcode', rules: [NL] }]);
        expect(results[0]).toMatchObject({ ok: true, message: "Set 1 rule(s) on 'Postcode'" });
        expect(rulesOf(doc, 'q_postcode')).toEqual([{ id: 'r_nl', when: { conditions: [{ fieldId: 'q_country', fieldType: 'dropdown', comparison: 'IS_EQUAL', value: 'Netherlands' }] }, then: { required: true } }]);
    });

    it('undo gives the document back, and redo the rules again', () => {
        const before = base();
        const { doc, inverse } = run([{ op: 'set_field_rules', fieldId: 'q_postcode', rules: [NL] }], before);
        expect(inverse.length).toBeGreaterThan(0);
        expect(applyOps(doc, inverse, { atomic: true }).doc).toEqual(before);
    });

    it('undoes a removal that took rules with it, on the question and on the ones that read it', () => {
        const withRule = withRules();
        const removed = run([{ op: 'remove_field', fieldId: 'q_country' }], withRule);
        expect(rulesOf(removed.doc, 'q_postcode')).toBeUndefined();
        const restored = applyOps(removed.doc, removed.inverse, { atomic: true }).doc;
        expect(rulesOf(restored, 'q_postcode')).toEqual(rulesOf(withRule, 'q_postcode'));
        expect(locateField(restored, 'q_country').field.title).toBe('Country');
    });

    it('refuses what a save would refuse, naming the problem', () => {
        const refuse = (rules: any[], fieldId = 'q_postcode', doc?: FormDoc) => {
            const { results } = run([{ op: 'set_field_rules', fieldId, rules }], doc);
            expect(results[0].ok).toBe(false);
            return results[0].message;
        };
        expect(
            refuse([
                { id: 'r', when: { conditions: [{ fieldId: 'q_note', comparison: 'IS_EMPTY' }] }, then: { required: true } },
                { ...NL, then: {} }
            ])
        ).toContain('at least one of');
        expect(refuse([{ id: 'bad id!', when: { expression: true }, then: { required: true } }])).toContain('pattern');
        expect(refuse(Array.from({ length: 9 }, (_, i) => ({ id: `r${i}`, when: { expression: true }, then: { required: true } })))).toContain('at most 8');
        expect(refuse([{ id: 'r', when: { expression: { var: 'nope' } }, then: { required: true } }])).toContain("'nope'");
        expect(refuse([{ id: 'r', when: { expression: true, operator: 'OR' }, then: { required: true } }])).toContain('operator');
        expect(refuse([{ id: 'r', when: { expression: true }, then: { title: '   ' } }])).toContain('title');
        expect(refuse([{ id: 'r', when: { expression: true }, then: { setValue: { const: 'x', expression: 1 } } }], 'q_qty')).toContain("'const' or 'expression'");
    });

    it('refuses value effects inside a repeating group and conditions from another group', () => {
        const doc = run([
            {
                op: 'add_group',
                pageId: 'p1',
                title: 'People',
                fields: [
                    { title: 'Name', type: 'short_text' },
                    { title: 'Age', type: 'number' }
                ]
            }
        ]).doc;
        const [name, age] = (doc.fields[0].properties!.fields as any[]).find((f) => f.type === 'group').properties.fields.map((f: any) => f.id);
        const lock = run([{ op: 'set_field_rules', fieldId: age, rules: [{ id: 'r1', when: { expression: true }, then: { readOnly: true } }] }], doc).results[0];
        expect(lock.message).toContain('repeating group');
        const outside = run([{ op: 'set_field_rules', fieldId: 'q_postcode', rules: [{ id: 'r1', when: { conditions: [{ fieldId: name, comparison: 'IS_EMPTY' }] }, then: { required: true } }] }], doc).results[0];
        expect(outside.message).toContain('once per item');
        const inside = run([{ op: 'set_field_rules', fieldId: age, rules: [{ id: 'r1', when: { conditions: [{ fieldId: name, comparison: 'IS_NOT_EMPTY' }] }, then: { required: true } }] }], doc).results[0];
        expect(inside.ok).toBe(true);
    });

    it('refuses a pipe to a question the form does not have, and accepts one it has', () => {
        const rule = (key: string) => [{ id: 'r', when: { expression: true }, then: { description: `Hi {{field:${key}}}` } }];
        expect(run([{ op: 'set_field_rules', fieldId: 'q_postcode', rules: rule('ghost') }]).results[0].message).toContain("pipes 'ghost'");
        expect(run([{ op: 'set_field_rules', fieldId: 'q_postcode', rules: rule('q_note') }]).results[0].ok).toBe(true);
    });

    it('clears with null, and refuses a rule id used on another question', () => {
        const cleared = run([{ op: 'set_field_rules', fieldId: 'q_postcode', rules: null }], withRules());
        expect(cleared.results[0].message).toBe("Cleared the rules on 'Postcode'");
        expect(rulesOf(cleared.doc, 'q_postcode')).toBeUndefined();
        expect(run([{ op: 'set_field_rules', fieldId: 'q_note', rules: [NL] }], withRules()).results[0].message).toContain('more than once');
    });
});

describe('rules a structural edit would leave dangling', () => {
    it('are dropped with a note when the question they read is removed', () => {
        const { doc, results } = run([{ op: 'remove_field', fieldId: 'q_country' }], withRules());
        expect(results[0].message).toBe("Removed 'Country' (and 1 field rule(s) that used it)");
        expect(rulesOf(doc, 'q_postcode')).toBeUndefined();
    });

    it('are dropped from a question made internal, and from the ones that read it', () => {
        const doc = run([{ op: 'set_field_rules', fieldId: 'q_total', rules: [{ id: 'r_t', when: { expression: true }, then: { setValue: { expression: { '*': [{ var: 'q_qty' }, 2] } } } }] }], withRules()).doc;
        const own = run([{ op: 'update_field', fieldId: 'q_postcode', patch: { internal: true } }], doc);
        expect(own.results[0].message).toContain('1 field rule(s)');
        expect(rulesOf(own.doc, 'q_postcode')).toBeUndefined();
        expect(rulesOf(own.doc, 'q_total')).toHaveLength(1);
        const read = run([{ op: 'update_field', fieldId: 'q_qty', patch: { internal: true } }], doc);
        expect(rulesOf(read.doc, 'q_total')).toBeUndefined();
    });

    it('are dropped when the option they set is removed or the options replaced', () => {
        const doc = run([{ op: 'set_field_rules', fieldId: 'q_pick', rules: [{ id: 'r_p', when: { expression: true }, then: { setValue: { const: 'c_a' } } }] }]).doc;
        const removed = run([{ op: 'remove_choice', fieldId: 'q_pick', choiceId: 'c_a' }], doc);
        expect(removed.results[0].message).toContain('1 field rule(s)');
        expect(rulesOf(removed.doc, 'q_pick')).toBeUndefined();
        const replaced = run([{ op: 'update_field', fieldId: 'q_pick', patch: { choices: ['X', 'Y'] } }], doc);
        expect(replaced.results[0].message).toContain('1 field rule(s)');
        expect(rulesOf(replaced.doc, 'q_pick')).toBeUndefined();
        const kept = run([{ op: 'update_field', fieldId: 'q_pick', patch: { choices: ['A', 'B', 'C'] } }], doc);
        expect(rulesOf(kept.doc, 'q_pick')).toHaveLength(1);
    });

    it('are dropped when the question moves into a repeating group, and undo brings them back', () => {
        const locked = run([{ op: 'set_field_rules', fieldId: 'q_qty', rules: [{ id: 'r_q', when: { expression: true }, then: { readOnly: true } }] }]).doc;
        const withGroup = run([{ op: 'add_group', pageId: 'p2', title: 'G', fields: [] }], locked).doc;
        const group = (withGroup.fields[1].properties!.fields as any[]).find((f) => f.type === 'group').id;
        const moved = run([{ op: 'move_field', fieldId: 'q_qty', toGroupId: group }], withGroup);
        expect(moved.results[0].message).toContain('1 field rule(s)');
        expect(rulesOf(moved.doc, 'q_qty')).toBeUndefined();
        const back = applyOps(moved.doc, moved.inverse, { atomic: true }).doc;
        expect(rulesOf(back, 'q_qty')).toEqual(rulesOf(withGroup, 'q_qty'));
    });

    it('are not copied with a duplicated page', () => {
        const doc = withRules();
        const copied = run([{ op: 'duplicate_page', pageId: 'p1' }], doc).doc;
        const copy = (copied.fields[1].properties!.fields as any[]).find((f) => f.title === 'Postcode');
        expect(copy.properties?.rules).toBeUndefined();
        expect(rulesOf(copied, 'q_postcode')).toHaveLength(1);
    });

    it('are swept out of the finished document even when no op named them', () => {
        const broken = thawed(withRules());
        // a rule on a question that a hand edit left pointing at nothing
        (locateField(broken, 'q_postcode').field.properties!.rules as any[])[0].when.conditions[0].fieldId = 'ghost';
        const { doc } = run([{ op: 'update_field', fieldId: 'q_note', patch: { internal: true } }], broken);
        expect(rulesOf(doc, 'q_postcode')).toBeUndefined();
    });
});

describe('field rule checks', () => {
    it('report problems with pointers and the question', () => {
        const doc = thawed(withRules());
        (locateField(doc, 'q_postcode').field.properties!.rules as any[])[0].when.conditions[0].fieldId = 'ghost';
        const problems = fieldRuleProblems(doc);
        expect(problems).toEqual([expect.objectContaining({ fieldId: 'q_postcode', path: '/0/when/conditions/0/fieldId', rule: 0 })]);
        expect(fieldRuleFixes(doc)).toEqual([{ path: [0, 1], rules: undefined, dropped: 1 }]);
    });

    it('count rules over the form cap, and cost over the budget', () => {
        const doc = base();
        const fields = doc.fields[0].properties!.fields as any[];
        // 13 questions with 8 rules each is over the 100 of a form
        for (let i = 0; i < 13; i++) fields.push({ id: `x${i}`, index: 5 + i, type: 'short_text', title: `X${i}`, properties: { rules: Array.from({ length: 8 }, (_, k) => ({ id: `x${i}r${k}`, when: { expression: true }, then: { required: true } })) } });
        expect(fieldRuleProblems(doc)[0].message).toContain('at most 100 rules');
        const costly = base();
        const wide = { '+': Array.from({ length: 100 }, () => ({ var: 'g.n' })) };
        (costly.fields[0].properties!.fields as any[]).push({ id: 'g', index: 5, type: 'group', title: 'G', properties: { repeat: { minItems: 1, maxItems: 50 }, fields: [{ id: 'n', index: 0, type: 'number', title: 'N' }] } });
        for (let i = 0; i < 10; i++)
            (costly.fields[0].properties!.fields as any[]).push({
                id: `y${i}`,
                index: 6 + i,
                type: 'number',
                title: `Y${i}`,
                properties: { rules: Array.from({ length: 8 }, (_, k) => ({ id: `y${i}r${k}`, when: { expression: { '>': [wide, 1] } }, then: { required: true } })) }
            });
        expect(
            fieldRuleProblems(costly)
                .map((p) => p.message)
                .join('\n')
        ).toContain('too long to check');
    });

    it('find a circle of set values, once', () => {
        const doc = base();
        const set = (id: string, from: string) => ({ id: `r_${id}`, when: { expression: true }, then: { setValue: { expression: { '+': [{ var: from }, 1] } } } });
        locateField(doc, 'q_qty').field.properties = { rules: [set('a', 'q_total')] } as any;
        locateField(doc, 'q_total').field.properties = { rules: [set('b', 'q_qty')] } as any;
        const circles = fieldRuleProblems(doc).filter((p) => p.message.includes('circle'));
        expect(circles).toHaveLength(1);
    });
});
