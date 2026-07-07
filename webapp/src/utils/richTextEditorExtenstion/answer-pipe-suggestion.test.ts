import { describe, expect, it } from 'vitest';

import { filterPipeSuggestionItems, PipeSuggestionItem } from './answer-pipe-suggestion';

const ITEMS: PipeSuggestionItem[] = [
    { kind: 'field', pipeKey: 'f1', label: 'Page 1 · What is your name?', group: 'Answers' },
    { kind: 'field', pipeKey: 'f2', label: 'Page 1 · Company size', group: 'Answers' },
    { kind: 'hidden', pipeKey: 'utm_source', label: 'utm_source', group: 'Hidden fields' }
];

describe('filterPipeSuggestionItems', () => {
    it('returns everything for an empty query', () => {
        expect(filterPipeSuggestionItems(ITEMS, '')).toHaveLength(3);
        expect(filterPipeSuggestionItems(ITEMS, '  ')).toHaveLength(3);
    });

    it('matches case-insensitively on the label', () => {
        expect(filterPipeSuggestionItems(ITEMS, 'NAME').map((i) => i.pipeKey)).toEqual(['f1']);
        expect(filterPipeSuggestionItems(ITEMS, 'utm').map((i) => i.pipeKey)).toEqual(['utm_source']);
    });

    it('returns empty when nothing matches', () => {
        expect(filterPipeSuggestionItems(ITEMS, 'zzz')).toEqual([]);
    });
});
