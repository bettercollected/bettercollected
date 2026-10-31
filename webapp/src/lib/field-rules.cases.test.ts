import { readFileSync } from 'fs';
import { resolve } from 'path';

import { FieldRuleStates, resolveFieldRules } from '@app/lib/field-rules';
import { StandardFormFieldDto } from '@app/models/dtos/form';

/**
 * The cases shared with the server (backend tests/app/services/test_field_rules_cases.py
 * runs the same file): what the rules decide for a set of answers, the answers
 * they leave and the states they give the questions. Field rule cases that also
 * check validation are in docs/spec/answer-validation.cases.json.
 */

type StateDump = Record<string, { locked?: true; required?: boolean; title?: string; description?: string }>;

interface Case {
    name: string;
    form: StandardFormFieldDto[];
    hiddenFields?: string[];
    hiddenValues?: Record<string, string>;
    today?: string;
    answers: Record<string, any>;
    answersAfter: Record<string, Record<string, any> | null>;
    states: StateDump;
}

const corpus = JSON.parse(readFileSync(resolve(__dirname, '../../../docs/spec/field-rules.cases.json'), 'utf-8')) as { cases: Case[] };

/** The states as the cases write them: question id (`group/question/item` in a repeating group). */
function dumpStates(states: FieldRuleStates): StateDump {
    const found: StateDump = {};
    const at = (key: string) => (found[key] = found[key] ?? {});
    const named = (key: string) => key.split('\u001f').join('/');
    states.locked.forEach((id) => (at(id).locked = true));
    states.required.forEach((required, key) => (at(named(key)).required = required));
    states.texts.forEach((texts, key) => Object.assign(at(named(key)), texts));
    return found;
}

describe('field rule cases shared with the server', () => {
    it('has uniquely named cases that say what they expect', () => {
        expect(corpus.cases.length).toBeGreaterThanOrEqual(40);
        expect(new Set(corpus.cases.map((c) => c.name)).size).toBe(corpus.cases.length);
        corpus.cases.forEach((c) => {
            expect(c.states, c.name).toBeDefined();
            expect(c.answersAfter, c.name).toBeDefined();
        });
    });

    it.each(corpus.cases.map((c) => [c.name, c] as const))('%s', (_name, testCase) => {
        const { answers, states } = resolveFieldRules(testCase.form, testCase.answers, testCase.hiddenValues ?? {}, testCase.today, testCase.hiddenFields ?? []);
        expect(dumpStates(states)).toEqual(testCase.states);
        Object.entries(testCase.answersAfter).forEach(([id, expected]) => {
            if (expected === null) expect(answers[id], id).toBeUndefined();
            else expect(answers[id], id).toEqual(expected);
        });
    });
});
