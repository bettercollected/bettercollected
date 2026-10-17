import { describe, expect, it } from 'vitest';

import { FormOutline, addQuestion, canMove, changeType, deleteQuestion, moveQuestion, outlineForBuild, outlineProblems, pagesWithGaps, pruneRules, renameQuestion, setChoices, setSectionTitle } from './ai-outline';

const outline = (): FormOutline => ({
    title: 'Volunteer sign-up',
    language: 'en',
    pages: [
        {
            key: 'p1',
            sectionTitle: 'About you',
            questions: [
                { key: 'name', label: 'What is your name?', type: 'short_text', required: true },
                { key: 'role', label: 'Which task?', type: 'multiple_choice', choices: ['Stalls', 'Other'] },
                { key: 'other', label: 'Which other task?', type: 'short_text' }
            ]
        },
        { key: 'p2', sectionTitle: 'Transport', questions: [{ key: 'car', label: 'Can you bring a car?', type: 'yes_no' }] },
        { key: 'p3', questions: [{ key: 'notes', label: 'Anything else?', type: 'long_text' }] }
    ],
    logic: [{ target: 'other', action: 'show', match: 'all', conditions: [{ question: 'role', comparison: 'equals', value: 'Other' }] }],
    jumps: [{ fromPage: 'p2', to: 'end', match: 'all', conditions: [{ question: 'car', comparison: 'equals', value: 'No' }] }]
});

const keys = (o: FormOutline) => o.pages.map((p) => p.questions.map((q) => q.key));

describe('outline edits', () => {
    it('renames a question and a section without touching the rest', () => {
        const renamed = setSectionTitle(renameQuestion(outline(), 'name', 'Your full name'), 'p2', 'Getting there');
        expect(renamed.pages[0].questions[0].label).toBe('Your full name');
        expect(renamed.pages[1].sectionTitle).toBe('Getting there');
        expect(renamed.logic).toHaveLength(1);
        expect(renamed.jumps).toHaveLength(1);
    });

    it('deleting a question drops the rules that used it', () => {
        const withoutRole = deleteQuestion(outline(), 'role');
        expect(keys(withoutRole)[0]).toEqual(['name', 'other']);
        expect(withoutRole.logic).toEqual([]);
        const withoutCar = deleteQuestion(outline(), 'car');
        expect(withoutCar.jumps).toEqual([]);
    });

    it('moves questions within and across pages, dropping rules put out of order', () => {
        const down = moveQuestion(outline(), 'name', 1);
        expect(keys(down)[0]).toEqual(['role', 'name', 'other']);
        // moving the condition's question after its target drops the rule
        const swapped = moveQuestion(outline(), 'other', -1);
        expect(keys(swapped)[0]).toEqual(['name', 'other', 'role']);
        expect(swapped.logic).toEqual([]);
        // past the end of a page: the start of the next one
        const across = moveQuestion(outline(), 'other', 1);
        expect(keys(across)).toEqual([['name', 'role'], ['other', 'car'], ['notes']]);
        expect(canMove(outline(), 'name', -1)).toBe(false);
        expect(canMove(outline(), 'notes', 1)).toBe(false);
        expect(moveQuestion(outline(), 'notes', 1)).toEqual(outline());
    });

    it('changing a type drops what no longer fits', () => {
        const changed = changeType(outline(), 'role', 'long_text');
        expect(changed.pages[0].questions[1]).toEqual({ key: 'role', label: 'Which task?', type: 'long_text' });
        expect(changed.logic).toEqual([]);
        const choice = changeType(outline(), 'notes', 'dropdown');
        expect(choice.pages[2].questions[0].type).toBe('dropdown');
    });

    it('adds a question with a fresh key and edits choices line by line', () => {
        const { outline: added, key } = addQuestion(outline(), 'p3');
        expect(added.pages[2].questions.map((q) => q.key)).toEqual(['notes', key]);
        expect(new Set(added.pages.flatMap((p) => p.questions.map((q) => q.key))).size).toBe(6);
        expect(outlineProblems(added)).toEqual(['Page 3, question 2 has no text.']);
        const choices = setChoices(outline(), 'role', ' Stalls \n\nCooking\n');
        expect(choices.pages[0].questions[1].choices).toEqual(['Stalls', 'Cooking']);
    });

    it('prunes jumps that go backwards or from a missing page', () => {
        const o = outline();
        o.jumps.push({ fromPage: 'p3', to: 'p1', match: 'all', conditions: [{ question: 'notes', comparison: 'is_answered' }] });
        o.jumps.push({ fromPage: 'gone', to: 'end', match: 'all', conditions: [{ question: 'notes', comparison: 'is_answered' }] });
        expect(pruneRules(o).jumps).toHaveLength(1);
    });

    it('finds the pages the AI may fill in', () => {
        expect(pagesWithGaps(outline())).toEqual([]);
        const noChoices = setChoices(outline(), 'role', 'Stalls');
        expect(pagesWithGaps(noChoices)).toEqual(['p1']);
        const passport = renameQuestion(outline(), 'notes', 'Your passport number');
        expect(pagesWithGaps(changeType(passport, 'notes', 'short_text'))).toEqual(['p3']);
        const email = changeType(outline(), 'notes', 'email');
        expect(pagesWithGaps(email)).toEqual(['p3']);
        expect(pagesWithGaps({ ...email, pages: email.pages.map((p) => ({ ...p, questions: p.questions.map((q) => (q.key === 'notes' ? { ...q, whyWeAsk: 'To reply.' } : q)) })) })).toEqual([]);
        // "Order ID" is not an ID number
        expect(pagesWithGaps(renameQuestion(outline(), 'name', 'Your order ID'))).toEqual([]);
    });

    it('trims the outline for the build', () => {
        const o = setSectionTitle(renameQuestion(outline(), 'name', '  Name  '), 'p1', '   ');
        const built = outlineForBuild(o);
        expect(built.pages[0].questions[0].label).toBe('Name');
        expect(built.pages[0].sectionTitle).toBeUndefined();
        expect(outlineProblems({ ...o, title: ' ' })).toContain('Give the form a title.');
    });
});
