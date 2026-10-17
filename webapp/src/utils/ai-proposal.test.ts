import { describe, expect, it } from 'vitest';

import { AIProposal, buildProposalChanges, proposalHighlights, toggleOp } from './ai-proposal';
import { BEFORE_FORM, PROPOSAL, empty } from './ai-proposal.fixtures';

describe('buildProposalChanges', () => {
    it('lists each change by page, with the op that makes it', () => {
        const groups = buildProposalChanges(PROPOSAL, BEFORE_FORM);
        expect(groups.map((g) => [g.label, g.changes.map((c) => [c.opIndex, c.text])])).toEqual([
            ['Form and theme', [[2, 'Changed theme to Plain']]],
            [
                'Page 1',
                [
                    [3, "Section title of page 1: 'About you'"],
                    [4, "Made 'Your name' required"]
                ]
            ],
            [
                'Page 2',
                [
                    [0, 'Added page 2'],
                    [1, "Added question 'Postcode' on page 2"]
                ]
            ]
        ]);
        expect(groups[1].pageId).toBe('page-1');
    });

    it('names theme colours, renames, removals and moves', () => {
        const proposal: AIProposal = {
            ...PROPOSAL,
            results: [{ index: 0, op: 'x', ok: true, message: 'x' }],
            steps: [
                {
                    index: 0,
                    diff: {
                        form: [
                            { path: '/title', before: 'Visit', after: 'Check-in' },
                            { path: '/theme/accent', before: '#fff', after: '#eee' },
                            { path: '/theme/style', before: 'classic', after: 'leaflet' }
                        ],
                        pages: empty(),
                        fields: {
                            ...empty(),
                            removed: [{ id: 'f1', path: '/pages/0/fields/0' }],
                            changed: [{ id: 'f1', path: '/pages/0/fields/0', changes: [{ path: '/pages/0/fields/0/title', before: 'Your name', after: 'Full name' }] }]
                        }
                    }
                }
            ]
        };
        const texts = buildProposalChanges(proposal, BEFORE_FORM).flatMap((g) => g.changes.map((c) => c.text));
        expect(texts).toEqual(["Renamed the form to 'Check-in'", 'Changed style to Leaflet', 'Changed the theme colours', "Removed question 'Your name' from page 1", "Question 'Your name': 'Full name'"]);
    });

    it('falls back to the result message when an op shows no difference', () => {
        const proposal: AIProposal = { ...PROPOSAL, steps: [] };
        const groups = buildProposalChanges(proposal, BEFORE_FORM);
        expect(groups).toHaveLength(1);
        expect(groups[0].label).toBe('Other changes');
        // the failed op is not offered
        expect(groups[0].changes.map((c) => c.opIndex)).toEqual([0, 1, 2, 3, 4]);
    });
});

describe('toggleOp', () => {
    it('brings the ops a choice builds on, and drops what builds on a dropped op', () => {
        expect(toggleOp(PROPOSAL, [2], 1, true)).toEqual([0, 1, 2]);
        expect(toggleOp(PROPOSAL, [0, 1, 2], 0, false)).toEqual([2]);
        expect(toggleOp(PROPOSAL, [0, 1, 2], 1, false)).toEqual([0, 2]);
    });
});

describe('proposalHighlights', () => {
    it('marks added and changed questions and counts changes per page', () => {
        const highlights = proposalHighlights(buildProposalChanges(PROPOSAL, BEFORE_FORM));
        expect(highlights.fields).toEqual({ 'f-post': 'added', f1: 'changed' });
        expect(highlights.pages).toEqual({ 'page-1': 2, 'page-2': 2 });
    });
});
