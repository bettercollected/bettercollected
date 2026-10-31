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

    it('trims as the server does: an ideographic space at the edge is refused', () => {
        expect(isTag('a\u3000')).toBe(false);
        expect(isTag('\u3000a')).toBe(false);
        expect(isTag('a\u3000b')).toBe(true);
    });

    // Format characters (Cf) reverse text in a view, hide in it, and defeat the comparison of two tags.
    it.each([
        ['U+061C Arabic letter mark', '\u061c'],
        ['U+200B zero-width space', '\u200b'],
        ['U+200C zero-width non-joiner', '\u200c'],
        ['U+200D zero-width joiner', '\u200d'],
        ['U+200E left-to-right mark', '\u200e'],
        ['U+200F right-to-left mark', '\u200f'],
        ['U+202A left-to-right embedding', '\u202a'],
        ['U+202B right-to-left embedding', '\u202b'],
        ['U+202C pop directional formatting', '\u202c'],
        ['U+202D left-to-right override', '\u202d'],
        ['U+202E right-to-left override', '\u202e'],
        ['U+2066 left-to-right isolate', '\u2066'],
        ['U+2067 right-to-left isolate', '\u2067'],
        ['U+2068 first strong isolate', '\u2068'],
        ['U+2069 pop directional isolate', '\u2069'],
        ['U+FEFF byte order mark', '\ufeff'],
        ['U+00AD soft hyphen', '\u00ad']
    ])('refuses %s, inside a tag and alone', (_name, character) => {
        expect(isTag(`re${character}d`)).toBe(false);
        expect(isTag(character)).toBe(false);
        expect(isTag(`${character}red`)).toBe(false);
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
