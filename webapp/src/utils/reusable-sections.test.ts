import { describe, expect, it } from 'vitest';

import { instanceContainers, instanceFields, libraryOf, plainTitle, replaceTarget, spliceOps, warningKey, whatKey } from './reusable-sections';

const mark = (instance: string, key: string, version = 1) => ({ library: { sectionId: 's1', version, key, instance } });
const q = (id: string, props: Record<string, unknown> = {}) => ({ id, type: 'short_text', title: id, properties: props }) as any;

const page = (fields: any[], containers: any[] = []) => ({ id: 'p1', properties: { fields, containers } }) as any;

describe('a copy of a library section in a page', () => {
    const p = page(
        [q('intro'), q('a', mark('i1', 'k1')), q('own'), q('b', mark('i1', 'k2')), q('c', mark('i2', 'k1')), q('outro')],
        [
            { id: 'box', type: 'panel', title: 'Box', fields: ['a'] },
            { id: 'mixed', type: 'panel', title: 'Mixed', fields: ['b', 'own'] }
        ]
    );

    it('is the questions that carry the same insert, in page order', () => {
        expect(instanceFields(p, 'i1').map((f) => f.id)).toEqual(['a', 'b']);
        expect(instanceFields(p, 'i2').map((f) => f.id)).toEqual(['c']);
        expect(instanceFields(p, 'nope')).toEqual([]);
        expect(libraryOf(p.properties.fields[1])).toMatchObject({ key: 'k1' });
        expect(libraryOf(p.properties.fields[0])).toBeUndefined();
    });

    it('has the containers that hold only its questions', () => {
        expect(instanceContainers(p, new Set(['a', 'b'])).map((c) => c.id)).toEqual(['box']);
    });

    it('is replaced where it was, counting the page without it', () => {
        expect(replaceTarget(p, 'i1')).toEqual({ replaceIds: ['a', 'b'], replaceContainerIds: ['box'], index: 1 });
        expect(replaceTarget(p, 'i2')).toEqual({ replaceIds: ['c'], replaceContainerIds: [], index: 4 });
        expect(replaceTarget(p, 'nope')).toBeNull();
    });
});

describe('the op that puts a fragment on a page', () => {
    it('is one splice_fields with only what is needed', () => {
        expect(spliceOps('p1', { fields: [{ id: 'x' }], containers: [] }, { index: 2 })).toEqual([{ op: 'splice_fields', pageId: 'p1', index: 2, fields: [{ id: 'x' }] }]);
        expect(spliceOps('p1', { fields: [{ id: 'x' }], containers: [{ id: 'c' }] }, { index: 0, replaceIds: ['a'], replaceContainerIds: ['c0'] })).toEqual([
            { op: 'splice_fields', pageId: 'p1', index: 0, fields: [{ id: 'x' }], containers: [{ id: 'c' }], replaceIds: ['a'], replaceContainerIds: ['c0'] }
        ]);
        // no place given: the end of the page
        expect(spliceOps('p1', { fields: [], containers: [] }, {})[0]).not.toHaveProperty('index');
    });
});

describe('texts', () => {
    it('reads a title as plain text, rich or not', () => {
        expect(plainTitle({ title: '  Name ' })).toBe('Name');
        expect(plainTitle({ title: { type: 'doc', content: [{ type: 'paragraph', content: [{ type: 'text', text: 'Full ' }, { type: 'answerPipe' }, { type: 'text', text: 'name' }] }] } })).toBe('Full name');
        expect(plainTitle({})).toBe('');
        expect(plainTitle(null)).toBe('');
    });

    it('names the sentence of a warning and of a change', () => {
        expect(warningKey('condition_dropped')).toBe('SECTIONS_LIB.WARNING.CONDITION_DROPPED');
        expect(whatKey('title')).toBe('SECTIONS_LIB.WHAT.TITLE');
    });
});
