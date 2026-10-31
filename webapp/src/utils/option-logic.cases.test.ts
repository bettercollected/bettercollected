import { readFileSync } from 'fs';
import { resolve } from 'path';

import { StandardFormFieldDto } from '@app/models/dtos/form';
import { clearUnavailableOptions, optionLogicWarnings, optionStates } from '@app/utils/option-logic';

/**
 * The cases shared with the server (backend tests/app/services/test_option_logic_cases.py
 * runs the same file): which options a question offers for a set of answers
 * (`hidden`, `noneLeft`), what the respondent page leaves after clearing the
 * selections of options that are not available (`answersAfter`, the 'clear'
 * checks) and the warnings the builder shows. Server validation ('validate'
 * checks) is the server's alone.
 */

interface Case {
    name: string;
    checks: string[];
    form: StandardFormFieldDto[];
    answers: Record<string, any>;
    locked?: string[];
    hidden: Record<string, string[]>;
    noneLeft: string[];
    answersAfter?: Record<string, Record<string, any> | null>;
    warnings?: Array<{ fieldId: string; code: string; optionId?: string }>;
}

const corpus = JSON.parse(readFileSync(resolve(__dirname, '../../../docs/spec/option-logic.cases.json'), 'utf-8')) as { cases: Case[] };

/** Respondents are served the form without internal questions. */
const served = (slides: StandardFormFieldDto[]): StandardFormFieldDto[] => slides.map((slide) => ({ ...slide, properties: { ...slide.properties, fields: (slide.properties?.fields ?? []).filter((field) => !field.internal) } }));

describe('option logic cases shared with the server', () => {
    it('has uniquely named cases that say what they expect', () => {
        expect(corpus.cases.length).toBeGreaterThanOrEqual(40);
        expect(new Set(corpus.cases.map((c) => c.name)).size).toBe(corpus.cases.length);
        corpus.cases.forEach((c) => {
            expect(c.hidden, c.name).toBeDefined();
            expect(c.noneLeft, c.name).toBeDefined();
            expect(c.checks.includes('clear'), c.name).toBe(c.answersAfter !== undefined);
        });
    });

    it.each(corpus.cases.map((c) => [c.name, c] as const))('offers: %s', (_name, testCase) => {
        const states = optionStates(served(testCase.form), testCase.answers, testCase.locked ?? []);
        const hidden = Object.fromEntries([...states.hidden].map(([id, options]) => [id, [...options].sort()]));
        expect(hidden).toEqual(Object.fromEntries(Object.entries(testCase.hidden).map(([id, options]) => [id, [...options].sort()])));
        expect([...states.noneLeft].sort()).toEqual([...testCase.noneLeft].sort());
    });

    it.each(corpus.cases.filter((c) => c.checks.includes('clear')).map((c) => [c.name, c] as const))('clears: %s', (_name, testCase) => {
        const { answers } = clearUnavailableOptions(served(testCase.form), testCase.answers, testCase.locked ?? []);
        Object.entries(testCase.answersAfter ?? {}).forEach(([id, expected]) => {
            if (expected === null) expect(answers[id], id).toBeUndefined();
            else expect(answers[id], id).toEqual(expected);
        });
    });

    it.each(corpus.cases.filter((c) => c.warnings).map((c) => [c.name, c] as const))('warns: %s', (_name, testCase) => {
        const key = (w: { fieldId: string; code: string; optionId?: string }) => JSON.stringify([w.fieldId, w.code, w.optionId ?? '']);
        expect(optionLogicWarnings(testCase.form).map(key).sort()).toEqual((testCase.warnings ?? []).map(key).sort());
    });
});
