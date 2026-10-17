import type { Draft } from 'immer';

import type { FieldPath } from '../date-rules';
import type { FieldLocation } from '../model';
import type { ApplyOptions, FormDoc, FormField } from '../types';

/**
 * What a handler works with. Lookups read `state`, the plain document as the
 * batch left it before this op (no draft proxies, so they cost nothing);
 * changes go through `draft`, along the path of what changes only, so
 * everything else keeps its reference.
 */
export interface OpContext {
    state: FormDoc;
    draft: Draft<FormDoc>;
    newId: () => string;
    options: ApplyOptions;
    /** Record what the op created: its id and the ids of the questions created with it. */
    noteCreated: (id: string, nested?: string[]) => void;
    /** Ids of the questions and pages the op removed (set through droppedReferencesNote). */
    referencesGone?: Set<string>;
    /** Hidden-field names the op removed (set through droppedHiddenReferencesNote). */
    hiddenGone?: Set<string>;
}

export type Handler<T> = (ctx: OpContext, op: T) => string;

/** The draft of the field at `path` (indexes into nested `fields` arrays). */
export function draftAt(draft: Draft<FormDoc>, path: FieldPath): Draft<FormField> {
    let node: any = draft.fields![path[0]];
    for (let i = 1; i < path.length; i++) node = node.properties.fields[path[i]];
    return node;
}

/** Draft of a located question. */
export function draftField(draft: Draft<FormDoc>, location: FieldLocation): Draft<FormField> {
    return draftAt(draft, location.parent ? [location.pagePos, location.parentPos, location.position] : [location.pagePos, location.position]);
}

/** Draft of the list holding a located question. */
export function draftContainer(draft: Draft<FormDoc>, location: FieldLocation): Draft<FormField>[] {
    const page: any = draft.fields![location.pagePos];
    return location.parent ? page.properties.fields[location.parentPos].properties.fields : page.properties.fields;
}

/** A field's properties, created when missing (backend `StandardFieldProperty(fields=[])`). */
export function ensureProperties(field: Draft<FormField>, withFields = true): NonNullable<Draft<FormField>['properties']> {
    if (field.properties == null) field.properties = withFields ? { fields: [] } : {};
    return field.properties!;
}

/** A page's or group's question list, created when missing. */
export function ensureFields(field: Draft<FormField>): Draft<FormField>[] {
    const properties = ensureProperties(field);
    if (properties.fields == null) properties.fields = [];
    return properties.fields as Draft<FormField>[];
}

/** Set or clear (undefined/null) a key, writing only on a change. */
export function setKey(target: any, key: string, value: any): void {
    if (value === undefined || value === null) {
        if (key in target) delete target[key];
    } else if (target[key] !== value) {
        target[key] = value;
    }
}

/**
 * Marks a message whose op must drop the date rules it left dangling
 * (backend `_dropped_rules_note`, which runs `prune_date_rules` on the
 * working form). The engine prunes once the op's draft is finished — reading
 * a whole draft costs far more than reading the plain result — and puts the
 * note in place of the mark.
 */
export const DROPPED_RULES_MARK = '\u0000dropped-rules';

export function droppedRulesNote(): string {
    return DROPPED_RULES_MARK;
}

/**
 * Marks a message whose op must drop the logic, jump and piping references
 * it left dangling (backend `_dropped_references_note`); the hidden-fields
 * variant also drops pipes of hidden fields no longer declared.
 */
export const DROPPED_REFERENCES_MARK = '\u0000dropped-references';
export const DROPPED_HIDDEN_REFERENCES_MARK = '\u0000dropped-hidden-references';
/** Mark the message: drop what refers to a missing question; count what referred to `gone`. */
export function droppedReferencesNote(ctx: OpContext, gone: Set<string>): string {
    ctx.referencesGone = gone;
    return DROPPED_REFERENCES_MARK;
}

/** Mark the message: drop pipes of undeclared hidden fields; count those of `gone`. */
export function droppedHiddenReferencesNote(ctx: OpContext, gone: Set<string>): string {
    ctx.hiddenGone = gone;
    return DROPPED_HIDDEN_REFERENCES_MARK;
}

/** The note for `dropped` date rules dropped by an op. */
export const droppedRulesText = (dropped: number) => (dropped ? ` (and ${dropped} date rule(s) that used it)` : '');

/*
 * Lists are replaced, not spliced: splicing a draft array reads every element
 * through the draft (one proxy each); a new array of the plain elements
 * costs nothing, and the elements keep their references.
 */
export const insertedAt = <T>(list: readonly T[], at: number, ...items: T[]): T[] => [...list.slice(0, at), ...items, ...list.slice(at)];
export const removedAt = <T>(list: readonly T[], at: number): T[] => [...list.slice(0, at), ...list.slice(at + 1)];

/** Put `items` as the questions of a page or group draft. */
export function setFields(owner: Draft<FormField>, items: readonly any[]): void {
    ensureProperties(owner).fields = items as any;
}

/** Draft of the page or group holding a located question. */
export function draftOwner(draft: Draft<FormDoc>, location: FieldLocation): Draft<FormField> {
    return location.parent ? draftAt(draft, [location.pagePos, location.parentPos]) : draft.fields![location.pagePos];
}
