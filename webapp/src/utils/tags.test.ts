import { describe, expect, it } from 'vitest';

import { TAGS_MAX, TAG_LENGTH_MAX, answerTags, duplicateIndex, isTag, joinedTags, tagKey, tagLength } from './tags';

describe('tags', () => {
    it('has the same hard caps as the server', () => {
        expect([TAGS_MAX, TAG_LENGTH_MAX]).toEqual([30, 40]);
    });

    it.each(['vegan', 'gluten free', 'café au lait', '日本語', 'a', 'x-y_z.1'])('takes %j', (tag) => {
        expect(isTag(tag)).toBe(true);
    });

    it.each([
        ['empty', ''],
        ['a leading space', ' a'],
        ['a trailing space', 'a '],
        ['a no-break space at the edge', ' a'],
        ['a comma', 'a,b'],
        ['a semicolon', 'a;b'],
        ['a tab', 'a\tb'],
        ['a line break', 'a\nb'],
        ['a control character', 'a\u0007b'],
        ['a C1 control character', 'a\u0085b'],
        ['a line separator', 'a b'],
        ['not text', 5]
    ])('refuses %s', (_name, tag) => {
        expect(isTag(tag)).toBe(false);
    });

    it('trims as the server does, not as JavaScript does (U+FEFF is not trimmed there)', () => {
        expect(isTag('﻿a')).toBe(true);
        expect(isTag('a　')).toBe(false);
    });

    it('compares ignoring case with toLowerCase, and finds the first repeat', () => {
        expect(tagKey('VeGaN')).toBe('vegan');
        expect(duplicateIndex(['a', 'b', 'c'])).toBeNull();
        expect(duplicateIndex(['a', 'b', 'A'])).toBe(2);
        expect(duplicateIndex(['x', 'y', 'y', 'x'])).toBe(2);
        expect(duplicateIndex([])).toBeNull();
    });

    it('counts characters the way the server does (a code point is one)', () => {
        expect(tagLength('abc')).toBe(3);
        expect(tagLength('😀😀')).toBe(2);
    });

    it('joins the tags for one export cell and reads an answer', () => {
        expect(joinedTags(['a', 'b'])).toBe('a; b');
        expect(answerTags({ type: 'tags', tags: ['a', 3, 'b'] })).toEqual(['a', 'b']);
        expect(answerTags({ type: 'tags' })).toBeUndefined();
        expect(answerTags(undefined)).toBeUndefined();
    });
});
