import { describe, expect, it } from 'vitest';

import { STAGES, aiStructuringNote, describeRules, describeStaffPart, describeWithheld, isAiWording, placeBox, progressPercent, stageStates, validateUpload } from '@app/utils/pdf-import';

describe('stageStates', () => {
    it('marks finished, current and waiting stages', () => {
        const states = stageStates('running', 'layout', ['analyze', 'text']);
        expect(states.analyze).toBe('done');
        expect(states.layout).toBe('current');
        expect(states.compile).toBe('waiting');
        expect(progressPercent(states)).toBe(Math.round((2.5 / STAGES.length) * 100));
    });
    it('marks the failed stage and completes everything on success', () => {
        expect(stageStates('failed', 'analyze', [])['analyze']).toBe('failed');
        expect(Object.values(stageStates('completed', null, [])).every((s) => s === 'done')).toBe(true);
    });
});

describe('describeRules', () => {
    it('explains applied rules in plain words and skips zeros', () => {
        const lines = describeRules({ other_option_gets_specify_field: 2, long_section_split: 0, unknown_rule: 1 });
        expect(lines).toEqual(['2 "Other" options got a "Please specify" field', 'unknown rule (1)']);
    });
    it('says tables and applicant blocks repeat and staff parts became internal fields', () => {
        expect(describeRules({ open_table_to_repeating_group: 1, applicant_blocks_to_repeating_group: 1, staff_only_to_internal_fields: 3 })).toEqual([
            '1 table became a repeating group: respondents add one entry per row',
            'The blocks for joint applicants became one repeating group with an entry per applicant',
            '3 staff-only fields became internal fields that staff fill in'
        ]);
    });
});

describe('describeStaffPart', () => {
    it('says what became of a staff-only part', () => {
        expect(describeStaffPart({ heading: 'For office use only', internal_fields: 2 })).toBe('For office use only: 2 internal fields that staff fill in on each submission. Respondents never see them.');
        expect(describeStaffPart({ heading: '', internal_fields: 1 })).toBe('Staff-only part: 1 internal field that staff fill in on each submission. Respondents never see it.');
        expect(describeStaffPart({ heading: 'Bank use', internal_fields: 0 })).toBe('Bank use: left out, nothing to fill in was found. Respondents never see it.');
    });
});

describe('placeBox', () => {
    it('scales PDF points to the displayed image', () => {
        expect(placeBox([100, 50, 300, 70], 600, 300)).toEqual({ left: 50, top: 25, width: 100, height: 10 });
    });
});

describe('validateUpload', () => {
    it('accepts PDFs and photos within the limit', () => {
        expect(validateUpload({ type: 'application/pdf', size: 1000, name: 'a.pdf' })).toBeNull();
        expect(validateUpload({ type: '', size: 1000, name: 'scan.JPG' })).toBeNull();
        expect(validateUpload({ type: 'text/plain', size: 10, name: 'a.txt' })).toMatch(/PDF/);
        expect(validateUpload({ type: 'application/pdf', size: 20 * 1024 * 1024, name: 'big.pdf' })).toMatch(/15 MB/);
    });
});

describe('isAiWording', () => {
    it('marks only boxes whose wording the AI wrote', () => {
        expect(isAiWording({ grounded: false })).toBe(true);
        expect(isAiWording({ grounded: true })).toBe(false);
        expect(isAiWording({})).toBe(false);
    });
});

describe('aiStructuringNote', () => {
    it('says whether the AI read the document', () => {
        expect(aiStructuringNote(true)).toBe('AI structuring: on');
        expect(aiStructuringNote(false)).toBe('AI structuring: off (built-in reader only)');
        expect(aiStructuringNote(undefined)).toBe('AI structuring: off (built-in reader only)');
    });
});

describe('describeWithheld', () => {
    it('lists pages with withheld words in page order', () => {
        expect(describeWithheld({ '3': 1, '1': 4, '2': 0 })).toEqual([
            { page: 1, text: 'Page 1: 4 words inside answer boxes looked like filled-in answers and were left out of the questions. Check the questions there.' },
            { page: 3, text: 'Page 3: 1 word inside answer boxes looked like filled-in answers and was left out of the questions. Check the questions there.' }
        ]);
        expect(describeWithheld(undefined)).toEqual([]);
    });
});
