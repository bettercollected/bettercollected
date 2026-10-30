import { describe, expect, it } from 'vitest';

import { shortReceiptNumber } from './receipt-number';

describe('shortReceiptNumber', () => {
    it('shows the first 8 characters of a UUID', () => {
        expect(shortReceiptNumber('0a1b2c3d-1111-4222-8333-444455556666')).toBe('#0a1b2c3d…');
    });

    it('shortens a number without dashes too, instead of showing it whole', () => {
        expect(shortReceiptNumber('0a1b2c3d111142228333444455556666')).toBe('#0a1b2c3d…');
    });

    it('cuts at 8 characters even when the first dash comes later', () => {
        expect(shortReceiptNumber('0a1b2c3d4e5f-1111')).toBe('#0a1b2c3d…');
    });

    it('is empty when there is no number', () => {
        expect(shortReceiptNumber(undefined)).toBe('');
        expect(shortReceiptNumber(null)).toBe('');
        expect(shortReceiptNumber('')).toBe('');
    });
});
