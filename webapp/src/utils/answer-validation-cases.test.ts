import { readFileSync } from 'fs';
import { resolve } from 'path';

import { StandardFormFieldDto } from '@app/models/dtos/form';
import { JUMP_TARGET_SUBMIT } from '@app/models/types/form-builder-shared';
import { getHiddenFieldIds, resolveJumpTargetId } from '@app/utils/conditional-logic';
import { parseScopedFieldId, validateGroupsInSlide } from '@app/utils/repeating-groups';
import { validateSlide } from '@app/utils/vvalidation-utils';

/**
 * The cases shared with the server's answer validation
 * (backend/tests/app/services/test_answer_validation.py runs all of them).
 * Here: the Required cases, through the same steps the respondent page takes
 * on "Next" (form-slide.tsx): hide questions by logic, validate the visible
 * ones, follow the page's jump or go to the next page.
 */

interface Problem {
    fieldId: string;
    rule: string;
    item?: number;
}

interface Case {
    name: string;
    checks: string[];
    form: StandardFormFieldDto[];
    answers: Record<string, any>;
    errors: Problem[];
}

const corpus = JSON.parse(readFileSync(resolve(__dirname, '../../../docs/spec/answer-validation.cases.json'), 'utf-8')) as { cases: Case[] };
const REQUIRED_CASES = corpus.cases.filter((c) => c.checks.includes('required'));

const RULES: Record<string, string> = { '0': 'required', REQUIRED: 'required', MIN_ITEMS: 'too_few_items', MAX_ITEMS: 'too_many_items' };

/** What the respondent page reports on its way through the form. */
function respondentProblems(slides: StandardFormFieldDto[], answers: Record<string, any>): Problem[] {
    const problems: Problem[] = [];
    const seen = new Set<number>();
    let index = 0;
    while (index >= 0 && index < slides.length && !seen.has(index)) {
        seen.add(index);
        const slide = slides[index];
        // Respondents are served the form without internal questions.
        const fields = (slide.properties?.fields ?? []).filter((field) => !field.internal);
        const hidden = getHiddenFieldIds(fields, answers);
        const visible = fields.filter((field) => !hidden.has(field.id));
        const invalid: Record<string, any[]> = {
            ...validateSlide({ ...slide, properties: { ...slide.properties, fields: visible } } as StandardFormFieldDto, answers),
            ...validateGroupsInSlide(visible, answers)
        };
        Object.entries(invalid).forEach(([key, codes]) => {
            const scoped = parseScopedFieldId(key);
            codes.forEach((code) => {
                const rule = RULES[String(code)] ?? String(code);
                problems.push(scoped ? { fieldId: scoped.childId, rule, item: scoped.index } : { fieldId: key, rule });
            });
        });
        const target = resolveJumpTargetId(slide, answers);
        if (target === JUMP_TARGET_SUBMIT) break;
        const targetIndex = target ? slides.findIndex((s) => s.id === target) : -1;
        index = targetIndex >= 0 ? targetIndex : index + 1;
    }
    return problems;
}

const sorted = (problems: Problem[]) => problems.map((p) => JSON.stringify([p.fieldId, p.rule, p.item ?? null])).sort();

describe('answer validation cases shared with the server', () => {
    it('has uniquely named cases, many of them about Required', () => {
        expect(new Set(corpus.cases.map((c) => c.name)).size).toBe(corpus.cases.length);
        expect(REQUIRED_CASES.length).toBeGreaterThanOrEqual(25);
    });

    it.each(REQUIRED_CASES.map((c) => [c.name, c] as const))('%s', (_name, testCase) => {
        expect(sorted(respondentProblems(testCase.form, testCase.answers))).toEqual(sorted(testCase.errors));
    });
});
