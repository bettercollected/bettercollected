'use client';

/**
 * Derived views of the form document (form-document.ts) that subscribe to
 * one page or question only. The document shares structure between edits,
 * so an entity that did not change keeps its reference and its subscribers
 * do not re-render.
 *
 * The per-entity atoms are cached in plain maps keyed by id (cleared when a
 * form is loaded anew).
 */
import { Atom, atom } from 'jotai';
import { selectAtom } from 'jotai/utils';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';

import { formDocAtom, onDocumentReset } from './form-document';

export interface EntityLocation {
    /** Position of the page in the document's pages. */
    pageIdx: number;
    /** Position of the question on its page (absent for a page). */
    fieldIdx?: number;
    /** Position of a repeating group's question within the group. */
    childIdx?: number;
}

const childrenOf = (field: StandardFormFieldDto | undefined) => (field?.properties?.fields ?? []) as StandardFormFieldDto[];

/** Page, question and group-question id -> where it is in the document. */
export const locationIndexAtom = atom((get) => {
    const index = new Map<string, EntityLocation>();
    (get(formDocAtom).fields ?? []).forEach((page, pageIdx) => {
        if (!page) return;
        index.set(page.id, { pageIdx });
        childrenOf(page).forEach((field, fieldIdx) => {
            if (!field) return;
            index.set(field.id, { pageIdx, fieldIdx });
            if (field.type === FieldTypes.GROUP) {
                childrenOf(field).forEach((child, childIdx) => {
                    if (child) index.set(child.id, { pageIdx, fieldIdx, childIdx });
                });
            }
        });
    });
    return index;
});

const sameIds = (a: string[], b: string[]) => a.length === b.length && a.every((id, i) => id === b[i]);

/** The ids of the pages, in order (a new array only when they change). */
export const pageIdsAtom = selectAtom(formDocAtom, (doc) => (doc.fields ?? []).map((page) => page.id), sameIds);

const fieldAtoms = new Map<string, Atom<StandardFormFieldDto | undefined>>();
const pageAtoms = new Map<string, Atom<StandardFormFieldDto | undefined>>();
const fieldIdsAtoms = new Map<string, Atom<string[]>>();
const pageShellAtoms = new Map<string, Atom<StandardFormFieldDto | undefined>>();

onDocumentReset(() => {
    fieldAtoms.clear();
    pageAtoms.clear();
    fieldIdsAtoms.clear();
    pageShellAtoms.clear();
});

/** A question (or a repeating group's question) by id; undefined when the form has none. */
export function fieldAtom(id: string): Atom<StandardFormFieldDto | undefined> {
    let cached = fieldAtoms.get(id);
    if (!cached) {
        cached = atom((get) => {
            const at = get(locationIndexAtom).get(id);
            if (!at || at.fieldIdx === undefined) return undefined;
            const field = childrenOf(get(formDocAtom).fields?.[at.pageIdx])[at.fieldIdx];
            return at.childIdx === undefined ? field : childrenOf(field)[at.childIdx];
        });
        fieldAtoms.set(id, cached);
    }
    return cached;
}

/** A page by id; undefined when the form has none. */
export function pageAtom(id: string): Atom<StandardFormFieldDto | undefined> {
    let cached = pageAtoms.get(id);
    if (!cached) {
        cached = atom((get) => {
            const at = get(locationIndexAtom).get(id);
            if (!at || at.fieldIdx !== undefined) return undefined;
            return get(formDocAtom).fields?.[at.pageIdx];
        });
        pageAtoms.set(id, cached);
    }
    return cached;
}

/** The ids of a page's questions, in order (a new array only when they change). */
export function fieldIdsOfPageAtom(id: string): Atom<string[]> {
    let cached = fieldIdsAtoms.get(id);
    if (!cached) {
        cached = selectAtom(pageAtom(id), (page) => childrenOf(page).map((field) => field.id), sameIds);
        fieldIdsAtoms.set(id, cached);
    }
    return cached;
}

/** A page without its questions (`properties.fields` left out). */
function shellOf(page: StandardFormFieldDto | undefined): StandardFormFieldDto | undefined {
    if (!page) return undefined;
    if (!page.properties) return { ...page };
    const { fields: _fields, ...properties } = page.properties;
    return { ...page, properties };
}

/** Same keys with the same values (by reference), `skip` left out. */
function shallowSame(a: Record<string, unknown> | undefined, b: Record<string, unknown> | undefined, skip: string): boolean {
    if (a === b) return true;
    if (!a || !b) return false;
    const keys = (value: Record<string, unknown>) => Object.keys(value).filter((key) => key !== skip);
    const ka = keys(a);
    return ka.length === keys(b).length && ka.every((key) => key in b && a[key] === b[key]);
}

const sameShell = (a: StandardFormFieldDto | undefined, b: StandardFormFieldDto | undefined) =>
    a === b ||
    (!!a &&
        !!b &&
        shallowSame(a as unknown as Record<string, unknown>, b as unknown as Record<string, unknown>, 'properties') &&
        shallowSame(a.properties as Record<string, unknown> | undefined, b.properties as Record<string, unknown> | undefined, 'fields'));

/**
 * A page's own settings (layout, theme, section title, jumps, ...) without
 * its questions: the same object while only its questions change, so a
 * component that shows the page around its questions does not re-render
 * when one of them is edited.
 */
export function pageShellAtom(id: string): Atom<StandardFormFieldDto | undefined> {
    let cached = pageShellAtoms.get(id);
    if (!cached) {
        cached = selectAtom(pageAtom(id), shellOf, sameShell);
        pageShellAtoms.set(id, cached);
    }
    return cached;
}
