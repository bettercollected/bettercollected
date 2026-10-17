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

onDocumentReset(() => {
    fieldAtoms.clear();
    pageAtoms.clear();
    fieldIdsAtoms.clear();
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
