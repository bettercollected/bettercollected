import { describe, expect, it } from 'vitest';

import { greetingPeriod, welcomeState } from './welcome-band';

const base = { formsTotal: 3, drafts: [], pendingRequests: 0, canEditForms: true, canReviewRequests: true };

describe('greetingPeriod', () => {
    it.each([
        [0, 'morning'],
        [5, 'morning'],
        [11, 'morning'],
        [12, 'afternoon'],
        [17, 'afternoon'],
        [18, 'evening'],
        [23, 'evening']
    ])("%i o'clock is %s", (hour, period) => {
        expect(greetingPeriod(hour)).toBe(period);
    });
});

describe('welcomeState', () => {
    it('waits for the forms list before saying anything', () => {
        expect(welcomeState({ ...base, formsTotal: undefined })).toEqual({ kind: 'loading' });
    });

    it('only greets when there are no forms: the empty state below has the one action', () => {
        expect(welcomeState({ ...base, formsTotal: 0 })).toEqual({ kind: 'no-forms' });
        expect(welcomeState({ ...base, formsTotal: 0, canEditForms: false, canReviewRequests: false })).toEqual({ kind: 'no-forms' });
    });

    it('does not offer to finish a draft to a member who cannot edit forms', () => {
        const drafts = [{ formId: 'f1', title: 'Open day' }];
        expect(welcomeState({ ...base, drafts, canEditForms: false })).toEqual({ kind: 'ready' });
    });

    it('puts what is waiting for the person before a draft', () => {
        const drafts = [{ formId: 'f1', title: 'Open day' }];
        expect(welcomeState({ ...base, drafts, pendingRequests: 2 })).toEqual({ kind: 'requests', count: 2 });
    });

    it('leaves requests out for a member who cannot review them', () => {
        const drafts = [{ formId: 'f1', title: 'Open day' }];
        expect(welcomeState({ ...base, drafts, pendingRequests: 2, canReviewRequests: false }).kind).toBe('draft');
    });

    it('offers to finish the most recent draft, and says how many there are', () => {
        const drafts = [
            { formId: 'f1', title: ' Open day ' },
            { formId: 'f2', title: 'Volunteers' }
        ];
        expect(welcomeState({ ...base, drafts })).toEqual({ kind: 'draft', formId: 'f1', title: 'Open day', count: 2 });
    });

    it('has nothing in particular to say when all is in order', () => {
        expect(welcomeState(base)).toEqual({ kind: 'ready' });
        expect(welcomeState({ ...base, pendingRequests: undefined })).toEqual({ kind: 'ready' });
    });
});
