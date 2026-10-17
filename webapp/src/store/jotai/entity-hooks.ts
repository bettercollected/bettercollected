'use client';

/**
 * Narrow hooks on the form document: a component that shows one page or
 * one question subscribes to that entity only (form-document-selectors.ts),
 * and acts on it by id through useFieldActions, which never subscribes. An
 * edit of one question then re-renders the components showing that
 * question, not every component that reads the form.
 */
import { useMemo, useState } from 'react';

import { Atom, atom, useAtomValue, useStore } from 'jotai';
import { selectAtom } from 'jotai/utils';

import { clone, jsonEqual } from '@app/lib/form-ops/model';
import type { FormField } from '@app/lib/form-ops/types';
import { StandardFormFieldDto } from '@app/models/dtos/form';
import { FieldConditionalLogic, IFormFieldValidation } from '@app/models/types/form-builder-shared';

import { FormDocument, builderFieldsAtom, commitBuilderFieldsAtom, dispatchAtom, formDocAtom } from './form-document';
import { fieldAtom, fieldIdsOfPageAtom, pageAtom, pageIdsAtom, pageShellAtom } from './form-document-selectors';

type Store = ReturnType<typeof useStore>;

const noEntityAtom = atom<StandardFormFieldDto | undefined>(undefined);
const noIdsAtom = atom<string[]>([]);

/** A question (or a repeating group's question) by id; re-renders only when it changes. */
export function useField(id: string | null | undefined): StandardFormFieldDto | undefined {
    return useAtomValue(id ? fieldAtom(id) : noEntityAtom);
}

/** A page by id, its questions included; re-renders when anything on it changes. */
export function usePage(id: string | null | undefined): StandardFormFieldDto | undefined {
    return useAtomValue(id ? pageAtom(id) : noEntityAtom);
}

/** A page's own settings without its questions (pageShellAtom); not re-rendered by question edits. */
export function usePageShell(id: string | null | undefined): StandardFormFieldDto | undefined {
    return useAtomValue(id ? pageShellAtom(id) : noEntityAtom);
}

/** The ids of a page's questions, in order; a new array only when they change. */
export function usePageFieldIds(id: string | null | undefined): string[] {
    return useAtomValue(id ? fieldIdsOfPageAtom(id) : noIdsAtom);
}

/** The ids of the pages, in order; a new array only when they change. */
export function usePageIds(): string[] {
    return useAtomValue(pageIdsAtom);
}

/**
 * A value derived from the form document; re-renders only when it changes
 * (by `equal`, default Object.is). `deps` are what `select` uses besides
 * the document.
 */
export function useDocValue<T>(select: (doc: FormDocument) => T, deps: unknown[], equal?: (a: T, b: T) => boolean): T {
    return useSelected(formDocAtom, select, deps, equal);
}

/**
 * A value derived from the builder's pages (the mutable copy its older
 * mutators edit, for values that hand those objects on); re-renders only
 * when it changes (by `equal`, default Object.is).
 */
export function useBuilderFieldsValue<T>(select: (fields: StandardFormFieldDto[]) => T, deps: unknown[], equal?: (a: T, b: T) => boolean): T {
    return useSelected(builderFieldsAtom, select, deps, equal);
}

const sameDeps = (a: unknown[], b: unknown[]) => a.length === b.length && a.every((dep, i) => Object.is(dep, b[i]));

/** `select` over `source`, as an atom made anew only when `deps` change. */
function useSelected<S, T>(source: Atom<S>, select: (value: S) => T, deps: unknown[], equal?: (a: T, b: T) => boolean): T {
    const [selected, setSelected] = useState(() => ({ deps, atom: selectAtom(source, select, equal) }));
    let current = selected;
    if (!sameDeps(current.deps, deps)) {
        current = { deps, atom: selectAtom(source, select, equal) };
        setSelected(current);
    }
    return useAtomValue(current.atom);
}

// ---------------------------------------------------------------------------
// Acting on one question by id
// ---------------------------------------------------------------------------

type FieldUpdate = (field: StandardFormFieldDto) => StandardFormFieldDto;

export interface ChangeFieldArgs {
    fieldId: string;
    update: FieldUpdate;
    coalesceKey?: string;
}

/** Where `fieldId` is in the builder's copy of the pages: the list it is in, and its position. */
function locateCopy(pages: StandardFormFieldDto[], fieldId: string): { list: StandardFormFieldDto[]; at: number } | null {
    for (const page of pages) {
        const fields = page?.properties?.fields ?? [];
        for (let at = 0; at < fields.length; at++) {
            if (fields[at]?.id === fieldId) return { list: fields, at };
            const children = fields[at]?.properties?.fields ?? [];
            const child = children.findIndex((entry) => entry?.id === fieldId);
            if (child >= 0) return { list: children, at: child };
        }
    }
    return null;
}

/**
 * Change one question as one op (`replace_field`, the op the builder's
 * older mutators' changes become): one undo step, merged with the previous
 * one while typing under the same `coalesceKey`. A change that leaves the
 * question as it is makes no step. When the ops engine refuses it, the
 * change goes through the builder's copy as the older mutators' changes do
 * (which then keeps the question as it was given). True when it changed the
 * form.
 */
export const changeFieldAtom = atom(null, (get, set, { fieldId, update, coalesceKey }: ChangeFieldArgs) => {
    const current = get(fieldAtom(fieldId));
    if (!current) return false;
    const next = update(current);
    if (next === current || jsonEqual(next, current)) return false;
    if (set(dispatchAtom, { ops: [{ op: 'replace_field', field: next as FormField }], coalesceKey })) return true;
    const pages = get(builderFieldsAtom);
    const found = locateCopy(pages, fieldId);
    if (!found) return false;
    // A copy: the builder's pages never share objects with the document.
    found.list[found.at] = clone(update(found.list[found.at]));
    return set(commitBuilderFieldsAtom, [...pages], coalesceKey ? { coalesceKey } : {});
});

/**
 * The per-question edits of the canvas and the inspector, by question id,
 * with the coalesce keys the builder's mutators use (typing into one text
 * is one undo step). Stable identity; they never subscribe to the form.
 */
export interface FieldActions {
    updateTitle: (fieldId: string, title: StandardFormFieldDto['title']) => boolean;
    /** `undefined` removes the description; '' shows an empty one. */
    updateDescription: (fieldId: string, description: string | undefined) => boolean;
    updateFieldPlaceholder: (fieldId: string, placeholder: string) => boolean;
    updateChoiceFieldValue: (fieldId: string, choiceId: string, value: string) => boolean;
    updateFieldProperty: (fieldId: string, property: string, value: unknown) => boolean;
    /** Merge into the answer rules; undefined, null, NaN or '' removes a rule. */
    updateFieldValidations: (fieldId: string, patch: Partial<IFormFieldValidation>) => boolean;
    updateFieldRequired: (fieldId: string, required: boolean) => boolean;
    updateFieldColSpan: (fieldId: string, colSpan: number) => boolean;
    updateFieldAttachment: (fieldId: string, attachment: StandardFormFieldDto['attachment']) => boolean;
    /** The question's show/hide rule; `undefined` clears it. */
    updateFieldLogic: (fieldId: string, logic: FieldConditionalLogic | undefined) => boolean;
}

const fieldActionsByStore = new WeakMap<Store, FieldActions>();

/** The per-question edits on `store` (see FieldActions). */
export function fieldActions(store: Store): FieldActions {
    const cached = fieldActionsByStore.get(store);
    if (cached) return cached;
    const change = (fieldId: string, update: FieldUpdate, coalesceKey?: string) => store.set(changeFieldAtom, { fieldId, update, coalesceKey });
    // As the builder's mutators write properties: a question without any gets `fields: []`.
    const withProperties = (field: StandardFormFieldDto, patch: Record<string, unknown>): StandardFormFieldDto => ({ ...field, properties: { ...(field.properties || { fields: [] }), ...patch } });
    const actions: FieldActions = {
        updateTitle: (fieldId, title) => change(fieldId, (field) => ({ ...field, title }), `title:${fieldId}`),
        updateDescription: (fieldId, description) => change(fieldId, (field) => ({ ...field, description }), `description:${fieldId}`),
        updateFieldPlaceholder: (fieldId, placeholder) =>
            change(
                fieldId,
                // The same text again (an input reporting its value on mount) is no edit.
                (field) => ((field.properties?.placeholder ?? '') === (placeholder ?? '') ? field : withProperties(field, { placeholder })),
                `placeholder:${fieldId}`
            ),
        updateChoiceFieldValue: (fieldId, choiceId, value) =>
            change(fieldId, (field) => withProperties(field, { choices: field.properties?.choices?.map((choice) => (choice.id === choiceId ? { ...choice, value } : choice)) }), `choice:${fieldId}:${choiceId}`),
        updateFieldProperty: (fieldId, property, value) => change(fieldId, (field) => ({ ...field, properties: { ...(field.properties || {}), [property]: value } }), `property:${fieldId}:${property}`),
        updateFieldValidations: (fieldId, patch) =>
            change(
                fieldId,
                (field) => {
                    const next: Record<string, unknown> = { ...(field.validations || {}) };
                    Object.entries(patch).forEach(([key, value]) => {
                        if (value === undefined || value === null || value === '' || (typeof value === 'number' && !Number.isFinite(value))) delete next[key];
                        else next[key] = value;
                    });
                    return { ...field, validations: next as IFormFieldValidation };
                },
                `validations:${fieldId}:${Object.keys(patch).sort().join(',')}`
            ),
        updateFieldRequired: (fieldId, required) => change(fieldId, (field) => ({ ...field, validations: { ...field.validations, required } })),
        updateFieldColSpan: (fieldId, colSpan) => change(fieldId, (field) => withProperties(field, { colSpan: Math.min(12, Math.max(1, colSpan)) })),
        updateFieldAttachment: (fieldId, attachment) => change(fieldId, (field) => ({ ...field, attachment }), `attachment:${fieldId}`),
        updateFieldLogic: (fieldId, logic) => change(fieldId, (field) => ({ ...field, properties: { ...(field.properties || {}), logic } }), `logic:${fieldId}`)
    };
    fieldActionsByStore.set(store, actions);
    return actions;
}

/** The per-question edits, by id (see FieldActions). Stable identity; never re-renders the caller. */
export function useFieldActions(): FieldActions {
    const store = useStore();
    return useMemo(() => fieldActions(store), [store]);
}
