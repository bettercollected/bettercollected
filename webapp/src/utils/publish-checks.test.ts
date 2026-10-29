import { readFileSync } from 'fs';
import { resolve } from 'path';

import { describe, expect, it } from 'vitest';

import { ThemeColors } from '@app/constants/theme';
import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';

import { THEME_PROBLEM_ID, asksForIdentity, getPublishProblems, hasWorkspaceTitle, problemsFromPublishError, requiresWorkspaceTitle, splitPublishProblems, templateReviewProblem, themeContrastProblems, visibleTitle, workspaceTitleProblems } from './publish-checks';

const q = (id: string, type: string, extra: Partial<StandardFormFieldDto> = {}): StandardFormFieldDto => ({ id, index: 0, type, title: 'Question', ...extra }) as StandardFormFieldDto;
const page = (...fields: StandardFormFieldDto[]) => [{ id: 'page', index: 0, type: FieldTypes.SLIDE, properties: { fields } } as StandardFormFieldDto];
const codes = (...fields: StandardFormFieldDto[]) => getPublishProblems(page(...fields)).map((p) => [p.code, p.fieldId]);

describe('publish checks: why we ask this', () => {
    it('needs a reason on email and phone questions', () => {
        expect(codes(q('e', FieldTypes.EMAIL))).toEqual([['missing_why_we_ask', 'e']]);
        expect(codes(q('p', FieldTypes.PHONE_NUMBER, { properties: { whyWeAsk: '  ' } }))).toEqual([['missing_why_we_ask', 'p']]);
        expect(codes(q('e', FieldTypes.EMAIL, { properties: { whyWeAsk: 'To send your receipt.' } }))).toEqual([]);
    });

    it('recognises ID-number questions narrowly', () => {
        for (const title of ['Uw BSN', 'Burgerservicenummer', 'Passport number', 'ID-nummer', 'Social security number']) {
            expect(asksForIdentity(q('t', FieldTypes.SHORT_TEXT, { title }))).toBe(true);
        }
        for (const title of ['Order ID', 'Passport photo attached?', 'Your idea', 'Bsnl']) {
            expect(asksForIdentity(q('t', FieldTypes.SHORT_TEXT, { title }))).toBe(false);
        }
        const rich = { type: 'doc', content: [{ type: 'paragraph', content: [{ type: 'text', text: 'Your passport no.' }] }] };
        expect(asksForIdentity(q('t', FieldTypes.NUMBER, { title: rich as any }))).toBe(true);
    });

    it('skips internal fields and checks repeating-group questions', () => {
        expect(codes(q('e', FieldTypes.EMAIL, { internal: true }))).toEqual([]);
        const group = q('g', FieldTypes.GROUP, { properties: { repeat: { maxItems: 3 } as any, fields: [q('child', FieldTypes.EMAIL)] } });
        expect(codes(group)).toEqual([['missing_why_we_ask', 'child']]);
    });
});

describe('publish checks: no required dead ends', () => {
    it('flags required content with nothing to answer', () => {
        expect(codes(q('i', FieldTypes.IMAGE_CONTENT, { validations: { required: true } }))).toEqual([['required_unanswerable', 'i']]);
        expect(codes(q('s', FieldTypes.TEXT, { validations: { required: true } }))).toEqual([['required_unanswerable', 's']]);
        expect(codes(q('g', FieldTypes.GROUP, { validations: { required: true } }))).toEqual([['required_unanswerable', 'g']]);
    });

    it('flags a required choice without options, not one with options or a yes/no', () => {
        expect(codes(q('d', FieldTypes.DROP_DOWN, { validations: { required: true }, properties: { choices: [{ id: 'c', value: '' }] } }))).toEqual([['required_unanswerable', 'd']]);
        expect(codes(q('d', FieldTypes.DROP_DOWN, { validations: { required: true }, properties: { choices: [{ id: 'c', value: 'A' }] } }))).toEqual([]);
        expect(codes(q('y', FieldTypes.YES_NO, { validations: { required: true } }))).toEqual([]);
    });

    it('does not flag required questions hidden by logic: respondents are only asked what they see', () => {
        const hidden = q('h', FieldTypes.SHORT_TEXT, { validations: { required: true }, properties: { logic: { action: 'SHOW', operator: 'AND', conditions: [{ fieldId: 'x', comparison: 'is_equal', value: 'y' }] } as any } });
        expect(codes(hidden)).toEqual([]);
    });
});

describe('publish checks: no pre-ticked answers', () => {
    it('blocks a yes/no or choice whose value picks one of its options', () => {
        expect(codes(q('c', FieldTypes.YES_NO, { value: 'Yes' }))).toEqual([['preset_answer', 'c']]);
        expect(
            codes(
                q('m', FieldTypes.MULTIPLE_CHOICE, {
                    value: 'subscribe',
                    properties: {
                        choices: [
                            { id: '1', value: 'Subscribe' },
                            { id: '2', value: 'No' }
                        ]
                    }
                })
            )
        ).toEqual([['preset_answer', 'm']]);
    });

    it('ignores a legacy title kept in value', () => {
        expect(codes(q('c', FieldTypes.YES_NO, { title: undefined, value: 'Do you agree to be contacted?' }))).toEqual([]);
    });
});

describe('publish checks: every question has a title', () => {
    const emptyDoc = { type: 'doc', content: [{ type: 'paragraph' }] };

    it('blocks a question with no title, an empty one or only spaces', () => {
        expect(codes(q('a', FieldTypes.SHORT_TEXT, { title: undefined }))).toEqual([['untitled_question', 'a']]);
        expect(codes(q('b', FieldTypes.LONG_TEXT, { title: emptyDoc as any }))).toEqual([['untitled_question', 'b']]);
        expect(codes(q('c', FieldTypes.DATE, { title: '   ' }))).toEqual([['untitled_question', 'c']]);
    });

    it('says where the question is, as no title can name it', () => {
        const slides = [
            { id: 'p1', index: 0, type: FieldTypes.SLIDE, properties: { fields: [q('a', FieldTypes.NUMBER)] } },
            { id: 'p2', index: 1, type: FieldTypes.SLIDE, properties: { fields: [q('b', FieldTypes.NUMBER), q('c', FieldTypes.NUMBER, { title: undefined })] } }
        ] as StandardFormFieldDto[];
        const [problem] = getPublishProblems(slides);
        expect(problem).toEqual({ code: 'untitled_question', fieldId: 'c', message: 'Question 2 on page 2 has no title. Write the question respondents should answer.' });
    });

    it('counts answer pipes and legacy plain titles as titles', () => {
        const piped = { type: 'doc', content: [{ type: 'paragraph', content: [{ type: 'answerPipe', attrs: { kind: 'field', pipeKey: 'x', label: 'Name' } }] }] };
        expect(codes(q('a', FieldTypes.SHORT_TEXT, { title: piped as any }))).toEqual([]);
        expect(codes(q('b', FieldTypes.SHORT_TEXT, { title: undefined, value: 'Your city' }))).toEqual([]);
    });

    it('does not ask content blocks or internal fields for a title', () => {
        for (const type of [FieldTypes.TEXT, FieldTypes.IMAGE_CONTENT, FieldTypes.VIDEO_CONTENT]) {
            expect(codes(q('t', type, { title: undefined }))).toEqual([]);
        }
        expect(codes(q('i', FieldTypes.SHORT_TEXT, { title: undefined, internal: true }))).toEqual([]);
    });

    it('checks the questions inside a repeating group', () => {
        const group = q('g', FieldTypes.GROUP, { properties: { repeat: { maxItems: 3 } as any, fields: [q('child', FieldTypes.SHORT_TEXT, { title: '' })] } });
        expect(codes(group)).toEqual([['untitled_question', 'child']]);
    });

    it('is a blocker for every form, old or new', () => {
        const problems = getPublishProblems(page(q('a', FieldTypes.SHORT_TEXT, { title: undefined })));
        expect(splitPublishProblems(problems, null).blocking.map((problem) => problem.code)).toEqual(['untitled_question']);
    });
});

describe('problemsFromPublishError', () => {
    it("reads the server's refusal", () => {
        const error = { status: 422, data: { code: 'form_not_publishable', message: 'x', problems: [{ code: 'missing_why_we_ask', fieldId: 'e', message: 'Add a reason' }] } };
        expect(problemsFromPublishError(error)).toEqual([{ code: 'missing_why_we_ask', fieldId: 'e', message: 'Add a reason' }]);
        expect(problemsFromPublishError({ status: 500, data: 'oops' })).toEqual([]);
    });
});

describe('themeContrastProblems', () => {
    it('lets every preset publish', () => {
        for (const theme of ThemeColors) expect(themeContrastProblems(theme)).toEqual([]);
    });

    it('stops a theme whose colours are hard to read, naming what fails', () => {
        expect(themeContrastProblems({ title: 'Pastel', primary: '#9CA3AF', secondary: '#1649E2', tertiary: '#E5E7EB', accent: '#FFFFFF' })).toEqual([
            {
                code: 'theme_contrast',
                fieldId: THEME_PROBLEM_ID,
                message: "The theme's colours are hard to read: questions and text on the page, answers in the input boxes and input borders. Use the suggested colours on the Design tab, or pick others."
            }
        ]);
    });

    it('blocks for every form, old or new', () => {
        const problems = themeContrastProblems({ title: 'Custom', primary: '#101828', secondary: '#FDE68A', tertiary: '#818CA0', accent: '#FFFFFF' });
        expect(splitPublishProblems(problems, undefined).blocking).toEqual(problems);
        expect(problems[0].message).toContain('white text on buttons and chosen answers and progress');
    });

    it('leaves a form without its own colours alone', () => {
        expect(themeContrastProblems(undefined)).toEqual([]);
        expect(themeContrastProblems({ title: 'Default' })).toEqual([]);
    });
});

describe('templateReviewProblem', () => {
    const refusal = { status: 422, data: { code: 'needs_review', message: 'x', problems: [{ code: 'needs_review', fieldId: null, importId: 'imp1', message: 'It was imported and still needs review.' }] } };

    it('reads the review problem, with the import it names, from the server refusal', () => {
        expect(templateReviewProblem(refusal)?.importId).toBe('imp1');
        expect(templateReviewProblem(refusal.data)?.code).toBe('needs_review');
    });

    it('is nothing for any other error', () => {
        expect(templateReviewProblem(undefined)).toBeUndefined();
        expect(templateReviewProblem({ status: 403, data: { code: 'forbidden' } })).toBeUndefined();
        expect(templateReviewProblem({ status: 422, data: { code: 'form_not_publishable', problems: refusal.data.problems } })).toBeUndefined();
        expect(templateReviewProblem({ status: 422, data: { code: 'needs_review', problems: [] } })).toBeUndefined();
    });
});

describe('workspaceTitleProblems', () => {
    it('names no problem for a workspace with a title', () => {
        expect(workspaceTitleProblems({ id: 'w', title: 'Acme Foundation' }, 2)).toEqual([]);
        expect(workspaceTitleProblems({ id: 'w', title: '  Acme  ' }, 2)).toEqual([]);
    });

    it('treats no title, an empty one and one of only whitespace as no title, even when the workspace has a readable handle', () => {
        for (const title of [undefined, null, '', ' ', ' \t\n ']) {
            const problems = workspaceTitleProblems({ id: 'w', title, workspaceName: 'acme-forms' } as any, 2);
            expect(problems.map((problem) => problem.code)).toEqual(['workspace_title_missing']);
            expect(problems[0].fieldId).toBe('');
        }
    });

    it('claims nothing while the workspace is still loading (no id)', () => {
        expect(workspaceTitleProblems(undefined, 2)).toEqual([]);
        expect(workspaceTitleProblems(null, 2)).toEqual([]);
        expect(workspaceTitleProblems({ title: '' }, 2)).toEqual([]);
    });

    it('is read from a refused publish like the other server problems', () => {
        const refusal = { status: 422, data: { code: 'form_not_publishable', problems: [{ code: 'workspace_title_missing', fieldId: null, message: 'Your workspace has no title yet.' }] } };
        expect(problemsFromPublishError(refusal).map((problem) => problem.code)).toEqual(['workspace_title_missing']);
    });

    it('is held to forms created under the rule (version 2 or later) only', () => {
        expect(requiresWorkspaceTitle(2)).toBe(true);
        expect(requiresWorkspaceTitle(3)).toBe(true);
        for (const version of [undefined, null, 0, 1]) {
            expect(requiresWorkspaceTitle(version)).toBe(false);
            expect(workspaceTitleProblems({ id: 'w', title: '' }, version)).toEqual([]);
        }
        expect(workspaceTitleProblems({ id: 'w', title: '' }, 2).map((problem) => problem.code)).toEqual(['workspace_title_missing']);
    });

    it('is a blocking problem for a form that is held to it', () => {
        const [problem] = workspaceTitleProblems({ id: 'w', title: '' }, 2);
        expect(splitPublishProblems([problem], 2)).toEqual({ blocking: [problem], recommended: [] });
    });

    it('leaves the "why we ask" rule as it was for older and newer forms', () => {
        const reason = { code: 'missing_why_we_ask', fieldId: 'f', message: 'm' } as any;
        expect(splitPublishProblems([reason], undefined)).toEqual({ blocking: [], recommended: [reason] });
        expect(splitPublishProblems([reason], 1)).toEqual({ blocking: [reason], recommended: [] });
        expect(splitPublishProblems([reason], 2)).toEqual({ blocking: [reason], recommended: [] });
    });
});

// The cases shared with the server (backend/tests/app/services/test_workspace_title_check.py): the builder's check and
// the server's agree on what is a title.
const titleCases = JSON.parse(readFileSync(resolve(__dirname, '../../../docs/spec/workspace-title.cases.json'), 'utf-8')) as { refused: Array<string | null>; accepted: string[] };

describe('hasWorkspaceTitle', () => {
    it.each(titleCases.refused)('is no title: %j', (title) => {
        expect(hasWorkspaceTitle(title)).toBe(false);
        expect(workspaceTitleProblems({ id: 'w', title }, 2).map((problem) => problem.code)).toEqual(['workspace_title_missing']);
    });

    it.each(titleCases.accepted)('is a title: %j', (title) => {
        expect(hasWorkspaceTitle(title)).toBe(true);
        expect(workspaceTitleProblems({ id: 'w', title }, 2)).toEqual([]);
    });

    it('shows only what can be seen', () => {
        expect(visibleTitle(' \u200bAc\u3164me\ufeff ')).toBe('Acme');
        expect(visibleTitle(undefined)).toBe('');
    });
});
