import { describe, expect, it } from 'vitest';

import { FieldTypes } from '@app/models/dtos/form';
import { formatFileSizeMb } from '@app/utils/file-utils';
import { DEFAULT_YES_NO_CHOICES, yesNoChoices } from '@app/utils/yes-no-choices';

const field = (choices?: Array<{ id: string; value?: string }>) => ({ id: 'f', index: 0, type: FieldTypes.YES_NO, ...(choices ? { properties: { fields: [], choices } } : {}) });

describe('yesNoChoices', () => {
    it('keeps the stored choices (their ids) when both Yes and No are there', () => {
        const stored = [
            { id: 'a', value: 'Yes' },
            { id: 'b', value: 'No' }
        ];
        expect(yesNoChoices(field(stored))).toBe(stored);
    });

    it.each([
        ['missing', undefined],
        ['empty', []],
        [
            'blank values',
            [
                { id: 'a', value: '' },
                { id: 'b', value: '' }
            ]
        ],
        ['only one', [{ id: 'a', value: 'Yes' }]]
    ])('falls back to Yes/No when choices are %s', (_label, choices) => {
        expect(yesNoChoices(field(choices as any))).toEqual(DEFAULT_YES_NO_CHOICES);
    });
});

describe('formatFileSizeMb', () => {
    it.each([
        [0, '< 10 KB'],
        [0.004, '< 10 KB'],
        [0.5, '512 KB'],
        [2.25, '2.25 MB'],
        [undefined, '']
    ])('%s MB reads as %s', (size, text) => {
        expect(formatFileSizeMb(size as any)).toBe(text);
    });
});
