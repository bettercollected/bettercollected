import { readFileSync } from 'fs';
import { resolve } from 'path';

import { StandardFormFieldDto } from '@app/models/dtos/form';
import { JUMP_TARGET_SUBMIT } from '@app/models/types/form-builder-shared';
import { validateAnswerRulesInSlide } from '@app/utils/answer-rules';
import { getHiddenFieldIds, logicSourcesById, resolveJumpTargetId } from '@app/utils/conditional-logic';
import { parseScopedFieldId, validateGroupsInSlide } from '@app/utils/repeating-groups';
import { validateSlide } from '@app/utils/vvalidation-utils';

/**
 * The cases shared with the server's answer validation
 * (backend/tests/app/services/test_answer_validation.py runs all of them).
 * Here: the Required and answer-rule cases, through the same steps the
 * respondent page takes on "Next" (form-slide.tsx): hide questions by logic,
 * validate the visible ones (Required first, then answer rules on the
 * questions Required has nothing against), follow the page's jump or go to
 * the next page. Cases marked 'server' only are the server's alone (answer
 * types, unknown ids) or differ on purpose ('clientDiffers' says why).
 */

interface Problem {
    fieldId: string;
    rule: string;
    item?: number;
}

interface Case {
    name: string;
    checks: string[];
    clientDiffers?: string;
    form: StandardFormFieldDto[];
    answers: Record<string, any>;
    errors: Problem[];
}

const corpus = JSON.parse(readFileSync(resolve(__dirname, '../../../docs/spec/answer-validation.cases.json'), 'utf-8')) as { cases: Case[] };
const CLIENT_CASES = corpus.cases.filter((c) => c.checks.includes('required') || c.checks.includes('rules'));

const RULES: Record<string, string> = { '0': 'required', REQUIRED: 'required', MIN_ITEMS: 'too_few_items', MAX_ITEMS: 'too_many_items' };

/** What the respondent page reports on its way through the form. */
function respondentProblems(slides: StandardFormFieldDto[], answers: Record<string, any>): Problem[] {
    const problems: Problem[] = [];
    const sources = logicSourcesById(slides);
    const seen = new Set<number>();
    let index = 0;
    while (index >= 0 && index < slides.length && !seen.has(index)) {
        seen.add(index);
        const slide = slides[index];
        // Respondents are served the form without internal questions.
        const fields = (slide.properties?.fields ?? []).filter((field) => !field.internal);
        const hidden = getHiddenFieldIds(fields, answers, sources);
        const visible = fields.filter((field) => !hidden.has(field.id));
        const invalid: Record<string, any[]> = {
            ...validateSlide({ ...slide, properties: { ...slide.properties, fields: visible } } as StandardFormFieldDto, answers),
            ...validateGroupsInSlide(visible, answers, sources)
        };
        Object.entries(validateAnswerRulesInSlide(visible, answers, sources)).forEach(([id, codes]) => {
            if (!invalid[id]) invalid[id] = codes;
        });
        Object.entries(invalid).forEach(([key, codes]) => {
            const scoped = parseScopedFieldId(key);
            codes.forEach((code) => {
                const rule = RULES[String(code)] ?? String(code).toLowerCase();
                problems.push(scoped ? { fieldId: scoped.childId, rule, item: scoped.index } : { fieldId: key, rule });
            });
        });
        const target = resolveJumpTargetId(slide, answers, sources);
        if (target === JUMP_TARGET_SUBMIT) break;
        const targetIndex = target ? slides.findIndex((s) => s.id === target) : -1;
        index = targetIndex >= 0 ? targetIndex : index + 1;
    }
    return problems;
}

const sorted = (problems: Problem[]) => problems.map((p) => JSON.stringify([p.fieldId, p.rule, p.item ?? null])).sort();

describe('answer validation cases shared with the server', () => {
    it('has uniquely named cases; those where the browser differs say why', () => {
        expect(new Set(corpus.cases.map((c) => c.name)).size).toBe(corpus.cases.length);
        expect(corpus.cases.filter((c) => c.checks.includes('required')).length).toBeGreaterThanOrEqual(25);
        expect(corpus.cases.filter((c) => c.checks.includes('rules')).length).toBeGreaterThanOrEqual(25);
        corpus.cases.filter((c) => c.clientDiffers).forEach((c) => expect(c.checks).toEqual(['server']));
    });

    it.each(CLIENT_CASES.map((c) => [c.name, c] as const))('%s', (_name, testCase) => {
        expect(sorted(respondentProblems(testCase.form, testCase.answers))).toEqual(sorted(testCase.errors));
    });
});
