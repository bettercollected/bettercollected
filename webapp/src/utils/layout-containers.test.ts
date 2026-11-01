/**
 * Layout containers (utils/layout-containers.ts): the shared structure cases
 * (docs/spec/layout-containers.cases.json, the same the backend's twin passes),
 * the blocks a page is drawn from, and the logic a container gives its
 * questions.
 */
import { existsSync, readFileSync } from 'fs';
import { resolve } from 'path';

import { describe, expect, it } from 'vitest';

import type { LayoutContainer, StandardFormFieldDto } from '@app/models/dtos/form';
import { CONTAINER_LOGIC, isFieldHiddenByLogic, logicSourcesById } from '@app/utils/conditional-logic';
import { blocksOf, containerLogicIndex, joinByPosition, layoutProblems, membersOf, repairContainers, runHeadings } from '@app/utils/layout-containers';

const CORPUS = resolve(__dirname, '../../../docs/spec/layout-containers.cases.json');
const corpus = existsSync(CORPUS) ? JSON.parse(readFileSync(CORPUS, 'utf8')) : null;

type Item = string | { id: string; internal?: boolean; group?: string[] };

function pageOf(spec: { fields: Item[]; containers?: LayoutContainer[] }, id = 'p1'): StandardFormFieldDto {
    const fields = spec.fields.map((item): StandardFormFieldDto => {
        if (typeof item === 'string') return { id: item, type: 'short_text', title: item } as any;
        if (item.group) return { id: item.id, type: 'group', title: item.id, properties: { repeat: { minItems: 1, maxItems: 3 }, fields: item.group.map((c) => ({ id: c, type: 'short_text', title: c })) } } as any;
        return { id: item.id, type: 'short_text', title: item.id, ...(item.internal ? { internal: true } : {}) } as any;
    });
    return { id, type: 'slide', properties: { fields, ...(spec.containers ? { containers: spec.containers } : {}) } } as any;
}

describe.skipIf(!corpus)('layout container structure cases', () => {
    it.each((corpus?.cases ?? []).map((c: any) => [c.name, c]))('%s', (_name, c: any) => {
        if (c.kind === 'repair') {
            const { containers, changed } = repairContainers(pageOf(c.page));
            expect({ containers: containers ?? null, changed }).toEqual(c.expect);
        } else if (c.kind === 'join') {
            const containers = joinByPosition(pageOf(c.page), c.fieldId);
            expect({ containers: containers ?? null }).toEqual(c.expect);
        } else {
            const pages = c.pages.map((spec: any, i: number) => pageOf(spec, `p${i + 1}`));
            expect({ problems: layoutProblems(pages) }).toEqual(c.expect);
        }
    });
});

const panel = (id: string, ...fields: string[]): LayoutContainer => ({ id, type: 'panel', title: id, fields });
const tabs = (id: string, ...lists: string[][]): LayoutContainer => ({ id, type: 'tabs', tabs: lists.map((fields, i) => ({ id: `${id}t${i + 1}`, title: `Tab ${i + 1}`, fields })) });

describe('blocksOf', () => {
    const page = pageOf({ fields: ['a', 'b', 'c', 'd', 'e'], containers: [panel('c1', 'b', 'c'), tabs('c2', ['d'], ['e'])] });
    const fields = (page.properties!.fields as StandardFormFieldDto[]).map((f) => ({ id: f.id }));

    it('draws plain questions and one block per container, at the first member', () => {
        const blocks = blocksOf(page, fields);
        expect(blocks.map((b) => (b.kind === 'field' ? b.field.id : b.container.id))).toEqual(['a', 'c1', 'c2']);
        const first = blocks[1];
        expect(first.kind === 'container' && first.members.map((m) => m.id)).toEqual(['b', 'c']);
        const strip = blocks[2];
        expect(strip.kind === 'container' && strip.tabs?.map((t) => t.members.map((m) => m.id))).toEqual([['d'], ['e']]);
    });

    it('leaves out what is hidden and a container with nothing left', () => {
        const visible = fields.filter((f) => !['b', 'c'].includes(f.id));
        expect(blocksOf(page, visible).map((b) => (b.kind === 'field' ? b.field.id : b.container.id))).toEqual(['a', 'c2']);
        const onlyOneTab = fields.filter((f) => f.id !== 'd');
        const strip = blocksOf(page, onlyOneTab).find((b) => b.kind === 'container' && b.container.id === 'c2');
        expect(strip?.kind === 'container' && strip.tabs?.map((t) => t.members.length)).toEqual([0, 1]);
    });

    it('is the plain list for a page without containers', () => {
        const plain = pageOf({ fields: ['a', 'b'] });
        expect(blocksOf(plain, [{ id: 'a' }, { id: 'b' }]).every((b) => b.kind === 'field')).toBe(true);
    });
});

describe('the logic of a container', () => {
    const rule = { action: 'SHOW', operator: 'AND', conditions: [{ fieldId: 'gate', fieldType: 'short_text', comparison: 'IS_EQUAL', value: 'yes' }] } as any;
    const page = pageOf({ fields: ['gate', 'a', 'b', 'c'], containers: [{ ...panel('c1', 'a', 'b'), logic: rule }] });
    const slides = [page];
    const sources = logicSourcesById(slides);
    const byId = Object.fromEntries((page.properties!.fields as StandardFormFieldDto[]).map((f) => [f.id, f]));
    const shown = { gate: { type: 'text', text: 'yes' } };
    const hidden = { gate: { type: 'text', text: 'no' } };

    it('hides its questions while its rule hides it, and only them', () => {
        expect(isFieldHiddenByLogic(byId.a, shown, sources)).toBe(false);
        expect(isFieldHiddenByLogic(byId.a, hidden, sources)).toBe(true);
        expect(isFieldHiddenByLogic(byId.b, hidden, sources)).toBe(true);
        expect(isFieldHiddenByLogic(byId.c, hidden, sources)).toBe(false);
    });

    it('keeps the sources map to the questions and ignores containers without a sources map', () => {
        expect(Object.keys(sources).sort()).toEqual(['a', 'b', 'c', 'gate']);
        expect(Object.getOwnPropertySymbols(sources)).toContain(CONTAINER_LOGIC);
        expect(isFieldHiddenByLogic(byId.a, hidden)).toBe(false);
    });

    it('only indexes logic that can hide', () => {
        expect(Object.keys(containerLogicIndex([page])).sort()).toEqual(['a', 'b']);
        expect(containerLogicIndex([pageOf({ fields: ['a'], containers: [panel('c1', 'a')] })])).toEqual({});
        expect(membersOf(tabs('t', ['a'], ['b', 'c']))).toEqual(['a', 'b', 'c']);
    });
});

describe('runHeadings', () => {
    const page = pageOf({ fields: ['a', 'b', 'c', 'd', 'e', 'f'], containers: [panel('c1', 'b', 'c'), tabs('c2', ['d'], ['e'])] });

    it('heads the run of a panel and each tab, and marks where questions outside start again', () => {
        expect(runHeadings(page, ['a', 'b', 'c', 'd', 'e', 'f'])).toEqual([undefined, 'c1', undefined, 'Tab 1', 'Tab 2', null]);
    });

    it('starts from the questions it is given (some may be left out)', () => {
        expect(runHeadings(page, ['c', 'd'])).toEqual(['c1', 'Tab 1']);
        expect(runHeadings(pageOf({ fields: ['a', 'b'] }), ['a', 'b'])).toEqual([undefined, undefined]);
    });
});
