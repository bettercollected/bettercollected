import { describe, expect, it } from 'vitest';

import { capitalize, isEmptyString, toEndDottedStr, toMidDottedStr } from '@app/utils/string-utils';

// A real unit test over shared string helpers. Importing via the `@app` alias
// also exercises the Vitest path-alias config.
describe('string-utils', () => {
    describe('capitalize', () => {
        it('upper-cases the first char and lower-cases the rest', () => {
            expect(capitalize('hELLO')).toBe('Hello');
        });

        it('handles a single character', () => {
            expect(capitalize('a')).toBe('A');
        });

        it('returns an empty string for falsy input', () => {
            expect(capitalize('')).toBe('');
        });
    });

    describe('isEmptyString', () => {
        it('is true only for a zero-length string', () => {
            expect(isEmptyString('')).toBe(true);
            expect(isEmptyString('x')).toBe(false);
        });
    });

    describe('toEndDottedStr', () => {
        it('truncates and appends an ellipsis past the limit', () => {
            expect(toEndDottedStr('hello world', 5)).toBe('hello...');
        });

        it('leaves short strings untouched', () => {
            expect(toEndDottedStr('hi', 5)).toBe('hi');
        });
    });

    describe('toMidDottedStr', () => {
        it('keeps head and tail, eliding the middle', () => {
            expect(toMidDottedStr('abcdefghijklmnopqrstuvwxyz', 5)).toBe('abcde...vwxyz');
        });

        it('returns the input when short enough', () => {
            expect(toMidDottedStr('short', 12)).toBe('short');
        });
    });
});
