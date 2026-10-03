import { describe, expect, it } from 'vitest';

import { MAX_FEEDBACK_MESSAGE_LENGTH, canSendFeedback, feedbackAuthor, statusTone, validateFeedbackStatuses } from './respondent-feedback';

describe('validateFeedbackStatuses (mirrors the backend)', () => {
    it('trims and collapses whitespace', () => {
        expect(validateFeedbackStatuses(['  Under   review ', 'Hired'])).toEqual({ statuses: ['Under review', 'Hired'] });
    });

    it('refuses empty, too long, duplicate (ignoring case) and too many', () => {
        expect(validateFeedbackStatuses(['  ']).error).toMatch(/1 to 40/);
        expect(validateFeedbackStatuses(['x'.repeat(41)]).error).toMatch(/1 to 40/);
        expect(validateFeedbackStatuses(['Hired', 'hired']).error).toMatch(/twice/);
        expect(validateFeedbackStatuses(Array.from({ length: 11 }, (_, i) => `s${i}`)).error).toMatch(/At most 10/);
    });

    it('accepts an empty list (message-only updates)', () => {
        expect(validateFeedbackStatuses([])).toEqual({ statuses: [] });
    });
});

describe('canSendFeedback', () => {
    it('needs a status, a message or both', () => {
        expect(canSendFeedback('', '   ')).toBe(false);
        expect(canSendFeedback('Selected', '')).toBe(true);
        expect(canSendFeedback(null, 'Welcome')).toBe(true);
    });

    it('caps the message length', () => {
        expect(canSendFeedback(null, 'x'.repeat(MAX_FEEDBACK_MESSAGE_LENGTH))).toBe(true);
        expect(canSendFeedback('Selected', 'x'.repeat(MAX_FEEDBACK_MESSAGE_LENGTH + 1))).toBe(false);
    });
});

describe('statusTone', () => {
    it('reads common words, negatives first', () => {
        expect(statusTone('Selected')).toBe('positive');
        expect(statusTone('Not selected')).toBe('negative');
        expect(statusTone('Rejected')).toBe('negative');
        expect(statusTone('Under review')).toBe('neutral');
        expect(statusTone(undefined)).toBe('neutral');
    });
});

describe('feedbackAuthor', () => {
    it('is the organisation, with a neutral fallback', () => {
        expect(feedbackAuthor('Acme Hiring')).toBe('Acme Hiring');
        expect(feedbackAuthor(null, 'Acme')).toBe('Acme');
        expect(feedbackAuthor(undefined)).toBe('The team');
    });
});
