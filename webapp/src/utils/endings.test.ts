import { describe, expect, it } from 'vitest';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { JUMP_TARGET_SUBMIT, LogicalOperator } from '@app/models/types/form-builder-shared';
import { computeFlowTraffic, resolveJump } from '@app/utils/conditional-logic';
import { countJumpsToEnding, defaultEnding, endingLabel, endingToShow, isEndingReachable, isJumpEndingMissing, jumpChoiceValue, jumpFromChoice, jumpsFallBackToDefault, withEndingIds } from '@app/utils/endings';
import { getPublishProblems } from '@app/utils/publish-checks';

const jump = (value: string, extra: Record<string, any> = {}) => ({
    operator: LogicalOperator.AND,
    conditions: [{ fieldId: 'member', fieldType: FieldTypes.YES_NO, comparison: 'IS_EQUAL', value }],
    target: JUMP_TARGET_SUBMIT,
    ...extra
});
const slides = (jumps: any[]): StandardFormFieldDto[] =>
    [
        { id: 'p1', index: 0, type: FieldTypes.SLIDE, properties: { fields: [{ id: 'member', index: 0, type: FieldTypes.YES_NO, title: 'Member?' }], jumps } },
        { id: 'p2', index: 1, type: FieldTypes.SLIDE, properties: { fields: [] } }
    ] as any;
const NO = { member: { boolean: false } };

describe('endings', () => {
    it('derives ids like the server: ending-<position>, skipping taken ones, keeping given ones', () => {
        const endings = [{ title: 'a' }, { id: 'ending-1' }, {}];
        expect(withEndingIds(endings).map((e) => e.id)).toEqual(['ending-2', 'ending-1', 'ending-3']);
        // the input is not changed, and the same list always gets the same ids
        expect(endings[0]).not.toHaveProperty('id');
        expect(withEndingIds(endings).map((e) => e.id)).toEqual(['ending-2', 'ending-1', 'ending-3']);
        expect(withEndingIds(null)).toEqual([]);
    });

    it('the default is the marked ending, else the first', () => {
        expect(defaultEnding([{ id: 'a' }, { id: 'b' }])?.id).toBe('a');
        expect(defaultEnding([{ id: 'a' }, { id: 'b', isDefault: true }])?.id).toBe('b');
        expect(defaultEnding([])).toBeUndefined();
    });

    it('shows the ending a jump chose, else the default (also when the chosen one is gone)', () => {
        const endings = [{ title: 'Thanks' }, { title: 'Sorry' }];
        expect(endingToShow(endings, 'ending-2')?.title).toBe('Sorry');
        expect(endingToShow(endings, undefined)?.title).toBe('Thanks');
        expect(endingToShow(endings, 'gone')?.title).toBe('Thanks');
        expect(endingToShow(null, 'x')).toBeUndefined();
    });

    it('labels endings by name, else by place, or "Thank you" when alone', () => {
        expect(endingLabel({ name: ' Eligible ' }, 0, 2)).toBe('Eligible');
        expect(endingLabel({ title: 'Sorry' }, 1, 2)).toBe('Ending 2');
        expect(endingLabel({}, 0, 1)).toBe('Thank you');
    });

    it('an ending is reachable when it is the default or a jump names it', () => {
        const endings = [{ id: 'a' }, { id: 'b' }, { id: 'c' }];
        const form = slides([jump('No', { endingId: 'b' })]);
        expect([0, 1, 2].map((i) => isEndingReachable(form, endings, i))).toEqual([true, true, false]);
        expect(countJumpsToEnding(form, 'b')).toBe(1);
        // a jump to a page never names an ending
        expect(countJumpsToEnding(slides([jump('No', { target: 'p2', endingId: 'b' })]), 'b')).toBe(0);
    });

    it('jumps to a deleted ending fall back to the default and still submit', () => {
        const form = slides([jump('No', { endingId: 'b' }), jump('Yes', { endingId: 'c' })]);
        const result = jumpsFallBackToDefault(form, 'b')!;
        expect(result.count).toBe(1);
        expect((result.slides[0].properties!.jumps as any[]).map((j) => [j.target, j.endingId])).toEqual([
            [JUMP_TARGET_SUBMIT, undefined],
            [JUMP_TARGET_SUBMIT, 'c']
        ]);
        // the input is untouched
        expect((form[0].properties!.jumps as any[])[0].endingId).toBe('b');
        expect(jumpsFallBackToDefault(form, 'nobody')).toBeNull();
        expect(isJumpEndingMissing(jump('No', { endingId: 'b' }) as any, [{ id: 'a' }])).toBe(true);
        expect(isJumpEndingMissing(jump('No') as any, [{ id: 'a' }])).toBe(false);
    });

    it('encodes a destination as one select value and back', () => {
        expect(jumpChoiceValue({ target: 'p2' })).toBe('p2');
        expect(jumpChoiceValue({ target: JUMP_TARGET_SUBMIT })).toBe(JUMP_TARGET_SUBMIT);
        const value = jumpChoiceValue({ target: JUMP_TARGET_SUBMIT, endingId: 'b' });
        expect(jumpFromChoice(value)).toEqual({ target: JUMP_TARGET_SUBMIT, endingId: 'b' });
        expect(jumpFromChoice('p2')).toEqual({ target: 'p2', endingId: undefined });
    });

    it('the respondent replay finds the deciding jump with its ending', () => {
        const form = slides([jump('No', { endingId: 'b' })]);
        expect(resolveJump(form[0], NO)).toMatchObject({ target: JUMP_TARGET_SUBMIT, endingId: 'b' });
        expect(resolveJump(form[0], { member: { boolean: true } })).toBeNull();
    });

    it('flow traffic counts where submissions ended', () => {
        const traffic = computeFlowTraffic(slides([jump('No', { endingId: 'b' })]), [NO, { member: { boolean: true } }, NO]);
        expect(traffic.endingVisits.get('b')).toBe(2);
        expect(traffic.endingVisits.get('')).toBe(1);
    });

    it('a jump to a missing ending blocks publishing (when endings are given)', () => {
        const form = slides([jump('No', { endingId: 'gone' })]);
        expect(getPublishProblems(form, [{ title: 'Thanks' }]).map((p) => [p.code, p.fieldId])).toEqual([['missing_ending', 'p1']]);
        expect(getPublishProblems(slides([jump('No', { endingId: 'ending-2' })]), [{}, {}])).toEqual([]);
        // without endings (an outline page check) it is not looked at
        expect(getPublishProblems(form)).toEqual([]);
    });
});
