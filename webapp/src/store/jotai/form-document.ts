'use client';

/**
 * The builder's form document: one immutable, StandardFormDto-shaped value
 * (pages and questions, welcome page, endings, theme, hidden fields, logo
 * settings) that every edit changes through a batch of form ops
 * (lib/form-ops). Each batch is one undo step: undo applies its inverse ops,
 * redo its ops again.
 *
 * Migration notes. The builder's older mutators still edit a mutable copy of
 * the pages in place (`builderFieldsAtom`) and then hand the whole array
 * over. That copy is kept apart from the document: a handed-over array is
 * compared with the document (`entityDiff`) and the differences are applied
 * as ops, so the document itself is never edited in place and unchanged
 * pages and questions keep their references. When the document changes
 * through ops (undo, redo, a dispatch, a remote change), the copy follows:
 * pages whose reference did not change keep their copy, the others are
 * copied again.
 *
 * Endings are changed with the engine's ending ops (`set_endings` from
 * the entity diff). What no op expresses yet, or a change the engine
 * refuses, is carried by local ops that never leave the builder:
 * `local_set_form_keys` and `local_set_fields`.
 */
import { atom } from 'jotai';

import { applied, applyOps, compactOps, entityDiff } from '@app/lib/form-ops';
import type { FormOp } from '@app/lib/form-ops';
import { immer } from '@app/lib/form-ops/apply';
import { formImageUrls } from '@app/lib/form-ops/images';
import { clone, isSlide, jsonEqual } from '@app/lib/form-ops/model';
import { StandardFormDto, StandardFormFieldDto } from '@app/models/dtos/form';
import { isStorageImageUrl, rememberStorageImageUrls } from '@app/utils/storage-image-urls';

import { initialFieldsState, initialFormState } from './form-defaults';

// Documents are not frozen while the older mutators and the form state
// still hand their objects to components that may change them.
immer.setAutoFreeze(false);

export type FormDocument = StandardFormDto;

/** The form-level parts of the document the builder's form state reads and writes. */
export const FORM_STATE_KEYS = ['title', 'description', 'welcomePage', 'thankyouPage', 'theme', 'hiddenFields', 'logoPosition', 'logoAlt', 'useWorkspaceLogo'] as const;
export type FormStateKey = (typeof FORM_STATE_KEYS)[number];

export const SET_FORM_KEYS = 'local_set_form_keys';
export const SET_FIELDS = 'local_set_fields';

/** Set form-level keys to these values (`undefined` removes a key). */
export interface SetFormKeysOp {
    op: typeof SET_FORM_KEYS;
    values: Record<string, unknown>;
}

/** Replace every page at once (when the engine cannot express or refuses a change). */
export interface SetFieldsOp {
    op: typeof SET_FIELDS;
    fields: StandardFormFieldDto[];
}

export type LocalOp = SetFormKeysOp | SetFieldsOp;
export type DocOp = FormOp | LocalOp;

export const isLocalOp = (op: DocOp): op is LocalOp => op.op === SET_FORM_KEYS || op.op === SET_FIELDS;

/** Undo history: at most this many steps. */
export const HISTORY_LIMIT = 50;
/**
 * Typing is one undo step, not one per keystroke: consecutive edits with the
 * same coalesce key (e.g. `description:<fieldId>`) within this window merge.
 */
export const UNDO_COALESCE_MS = 1000;

export interface HistoryStep {
    forward: DocOp[];
    inverse: DocOp[];
    label?: string;
    coalesceKey?: string;
    /** When the step was last extended (ms). */
    at: number;
    /** The pages the builder handed over for this step (compatibility path; see undoIfLatestAtom). */
    builderFields?: StandardFormFieldDto[];
    /**
     * The documents before and after the step (shared structure, so cheap):
     * when its ops cannot be applied any more, undo and redo put these back
     * exactly instead of getting stuck.
     */
    before: FormDocument;
    after: FormDocument;
}

export interface DocHistory {
    steps: HistoryStep[];
    /** How many steps are applied; steps after it can be redone. */
    cursor: number;
    /** May the latest step still absorb typing (false after undo, redo and loading). */
    open: boolean;
}

const emptyHistory = (): DocHistory => ({ steps: [], cursor: 0, open: false });

const initialDocument = { ...clone(initialFormState), formId: '', fields: clone(initialFieldsState) } as FormDocument;

export const formDocAtom = atom<FormDocument>(initialDocument);
export const docHistoryAtom = atom<DocHistory>(emptyHistory());
/** The mutable copy of the pages the builder's older mutators edit in place. */
export const builderFieldsAtom = atom<StandardFormFieldDto[]>(initialFieldsState);

export const canUndoAtom = atom((get) => get(docHistoryAtom).cursor > 0);
export const canRedoAtom = atom((get) => {
    const history = get(docHistoryAtom);
    return history.cursor < history.steps.length;
});

// ---------------------------------------------------------------------------
// Applying ops
// ---------------------------------------------------------------------------

export interface DocApplyResult {
    ok: boolean;
    doc: FormDocument;
    /** Ops that take `doc` back to the document the ops started from. */
    inverse: DocOp[];
}

function applyLocal(doc: FormDocument, op: LocalOp): { doc: FormDocument; inverse: LocalOp | null } {
    if (op.op === SET_FIELDS) {
        if (op.fields === doc.fields) return { doc, inverse: null };
        return { doc: { ...doc, fields: op.fields }, inverse: { op: SET_FIELDS, fields: doc.fields } };
    }
    const current = doc as unknown as Record<string, unknown>;
    const entries = Object.entries(op.values).filter(([key, value]) => current[key] !== value);
    if (!entries.length) return { doc, inverse: null };
    const next: Record<string, unknown> = { ...current };
    const previous: Record<string, unknown> = {};
    for (const [key, value] of entries) {
        previous[key] = current[key];
        if (value === undefined) delete next[key];
        else next[key] = value;
    }
    return { doc: next as unknown as FormDocument, inverse: { op: SET_FORM_KEYS, values: previous } };
}

/** Form-level keys whose earlier value some op can set again (see entityDiff). */
const EXPRESSED_FORM_KEYS = new Set(['title', 'description', 'welcomePage', 'thankyouPage', 'theme', 'hiddenFields', 'logoPosition', 'logoAlt', 'useWorkspaceLogo', 'settings']);

/**
 * The engine's inverse cannot clear a form-level key that was absent before
 * (a first theme, say), nor restore keys no op sets: a local op puts those
 * back exactly.
 */
function unexpressedRestore(prev: FormDocument, touched: Set<string>): SetFormKeysOp | null {
    const values: Record<string, unknown> = {};
    const before = prev as unknown as Record<string, unknown>;
    for (const key of touched) if (!EXPRESSED_FORM_KEYS.has(key) || before[key] == null) values[key] = before[key];
    return Object.keys(values).length ? { op: SET_FORM_KEYS, values } : null;
}

/**
 * Apply `ops` to `doc` (never changed itself). Runs of engine ops are applied
 * atomically: when any op is refused, nothing is applied and `ok` is false.
 */
export function applyDocOps(doc: FormDocument, ops: DocOp[], withInverse = true): DocApplyResult {
    let current = doc;
    const inverses: DocOp[][] = [];
    let i = 0;
    while (i < ops.length) {
        const op = ops[i];
        if (isLocalOp(op)) {
            const result = applyLocal(current, op);
            if (result.inverse) inverses.unshift([result.inverse]);
            current = result.doc;
            i++;
            continue;
        }
        let j = i;
        while (j < ops.length && !isLocalOp(ops[j])) j++;
        const batch = ops.slice(i, j) as FormOp[];
        let result;
        try {
            result = applyOps(current, batch, { atomic: true, skipInverse: !withInverse, isStorageImageUrl });
        } catch {
            return { ok: false, doc, inverse: [] };
        }
        if (!applied(result.results, true)) return { ok: false, doc, inverse: [] };
        if (result.doc !== current) {
            const restore = unexpressedRestore(current, result.touched.form);
            inverses.unshift(restore ? [...result.inverse, restore] : result.inverse);
        }
        current = result.doc;
        i = j;
    }
    return { ok: true, doc: current, inverse: inverses.flat() };
}

/** Does `later` set everything `earlier` did (so `earlier` can be left out)? */
function folds(earlier: DocOp, later: DocOp): boolean {
    if (isLocalOp(earlier) || isLocalOp(later)) {
        if (earlier.op !== later.op) return false;
        if (earlier.op === SET_FIELDS) return true;
        return Object.keys((earlier as SetFormKeysOp).values).every((key) => key in (later as SetFormKeysOp).values);
    }
    return compactOps([earlier, later]).length === 1;
}

/** `ops` without the ops that a following op overrides (see lib/form-ops/compact.ts). */
export function compactDocOps(ops: DocOp[]): DocOp[] {
    const out: DocOp[] = [];
    for (const op of ops) {
        while (out.length && folds(out[out.length - 1], op)) out.pop();
        out.push(op);
    }
    return out;
}

/**
 * Local ops that turn `from` into `to` exactly (pages and form-level keys
 * by reference): the fallback when an inverse or a redo cannot be applied.
 */
export function exactRestore(from: FormDocument, to: FormDocument): LocalOp[] {
    const ops: LocalOp[] = [];
    if (from.fields !== to.fields) ops.push({ op: SET_FIELDS, fields: to.fields });
    const a = from as unknown as Record<string, unknown>;
    const b = to as unknown as Record<string, unknown>;
    const values: Record<string, unknown> = {};
    for (const key of new Set([...Object.keys(a), ...Object.keys(b)])) if (key !== 'fields' && a[key] !== b[key]) values[key] = b[key];
    if (Object.keys(values).length) ops.push({ op: SET_FORM_KEYS, values });
    return ops;
}

// ---------------------------------------------------------------------------
// Planning a change from a target document (the compatibility path)
// ---------------------------------------------------------------------------

export interface PlannedChange {
    doc: FormDocument;
    forward: DocOp[];
    inverse: DocOp[];
}

const noChange = (doc: FormDocument): PlannedChange => ({ doc, forward: [], inverse: [] });

function chain(first: PlannedChange, second: PlannedChange): PlannedChange {
    return { doc: second.doc, forward: [...first.forward, ...second.forward], inverse: [...second.inverse, ...first.inverse] };
}

const hasNonPages = (fields: StandardFormFieldDto[] | undefined) => !!fields?.some((entry) => !isSlide(entry));

/** Same non-page entries, at the same positions. */
function sameNonPages(a: StandardFormFieldDto[] | undefined, b: StandardFormFieldDto[] | undefined): boolean {
    const list = (fields: StandardFormFieldDto[] | undefined) => (fields ?? []).flatMap((entry, position) => (isSlide(entry) ? [] : [[position, entry] as const]));
    const x = list(a);
    const y = list(b);
    return x.length === y.length && x.every(([position, entry], i) => position === y[i][0] && jsonEqual(entry, y[i][1]));
}

/** The ops that give `doc` these pages: entity ops where possible, else one local replace. */
export function planFields(doc: FormDocument, fields: StandardFormFieldDto[]): PlannedChange {
    if (fields === doc.fields) return noChange(doc);
    let ops: FormOp[] | null = null;
    try {
        ops = entityDiff(doc, { ...doc, fields });
    } catch {
        ops = null;
    }
    // The engine plans pages only: top-level entries that are not pages
    // (older forms) must come out exactly as handed over, else the whole
    // list is replaced.
    const extras = hasNonPages(doc.fields) || hasNonPages(fields);
    if (ops && !ops.length && !extras) return noChange(doc);
    if (ops) {
        const result = ops.length ? applyDocOps(doc, ops) : { ok: true, doc, inverse: [] };
        if (result.ok && (!extras || sameNonPages(result.doc.fields, fields))) {
            if (result.doc === doc) return noChange(doc);
            return { doc: result.doc, forward: ops, inverse: result.inverse };
        }
    }
    const forward: DocOp[] = [{ op: SET_FIELDS, fields: clone(fields) ?? [] }];
    const result = applyDocOps(doc, forward);
    return { doc: result.doc, forward, inverse: result.inverse };
}

/**
 * The ops that give `doc` these form-level values (`undefined` removes a
 * key): entity ops first, then a local op for what they did not express or
 * were refused for, so that the document ends up with exactly these values.
 */
export function planFormKeys(doc: FormDocument, values: Partial<Record<FormStateKey, unknown>>): PlannedChange {
    const keys = Object.keys(values) as FormStateKey[];
    const current = doc as unknown as Record<string, unknown>;
    if (keys.every((key) => current[key] === values[key])) return noChange(doc);
    const target: Record<string, unknown> = { ...current };
    for (const key of keys) {
        if (values[key] === undefined) delete target[key];
        else target[key] = values[key];
    }
    let first = noChange(doc);
    try {
        const ops = entityDiff(doc, target as unknown as FormDocument);
        if (ops.length) {
            const result = applyDocOps(doc, ops);
            if (result.ok) first = { doc: result.doc, forward: ops, inverse: result.inverse };
        }
    } catch {
        first = noChange(doc);
    }
    const after = first.doc as unknown as Record<string, unknown>;
    // Endings set by the engine come back in its shape (ids given, unset
    // and unknown keys dropped, as the server stores them): that is the value.
    const endingsSet = first.forward.some((op) => op.op === 'set_endings') && Array.isArray(after.thankyouPage) && Array.isArray(values.thankyouPage);
    const rest: Record<string, unknown> = {};
    for (const key of keys) if (!(key === 'thankyouPage' && endingsSet) && (!jsonEqual(after[key], values[key]) || (after[key] === undefined) !== (values[key] === undefined))) rest[key] = clone(values[key]);
    if (!Object.keys(rest).length) return first;
    const local: DocOp[] = [{ op: SET_FORM_KEYS, values: rest }];
    const result = applyDocOps(first.doc, local);
    return chain(first, { doc: result.doc, forward: local, inverse: result.inverse });
}

// ---------------------------------------------------------------------------
// The builder's copy of the pages
// ---------------------------------------------------------------------------

/** Document page -> the builder's mutable copy of it. */
const builderCopies = new WeakMap<object, StandardFormFieldDto>();

const copyOf = <T>(value: T): T => (typeof structuredClone === 'function' ? structuredClone(value) : clone(value));

/** The builder's copy of `fields`: unchanged pages keep their copy, the others are copied. */
function builderCopy(fields: StandardFormFieldDto[] | undefined): StandardFormFieldDto[] {
    return (fields ?? []).map((page) => {
        let copy = builderCopies.get(page);
        if (!copy) {
            copy = copyOf(page);
            builderCopies.set(page, copy);
        }
        return copy;
    });
}

/** After the builder handed over `builderFields`: its pages are the copies of the document's pages. */
function rememberCopies(prev: FormDocument, next: FormDocument, builderFields: StandardFormFieldDto[]) {
    const kept = new Set<object>(next.fields ?? []);
    for (const page of prev.fields ?? []) if (!kept.has(page)) builderCopies.delete(page);
    const byId = new Map(builderFields.filter(Boolean).map((page) => [page.id, page]));
    for (const page of next.fields ?? []) {
        const copy = byId.get(page.id);
        if (copy) builderCopies.set(page, copy);
        else builderCopies.delete(page);
    }
}

// ---------------------------------------------------------------------------
// Committing
// ---------------------------------------------------------------------------

type Setter = <V>(target: any, value: V) => void;

const resetListeners = new Set<() => void>();
/** Called when the document is loaded anew (caches keyed by id are dropped). */
export function onDocumentReset(listener: () => void) {
    resetListeners.add(listener);
    return () => resetListeners.delete(listener);
}

/** The step a new one with this key, made at `at`, would merge into (typing), if any. */
function mergeTarget(history: DocHistory, coalesceKey: string | undefined, at: number): HistoryStep | null {
    const last = history.steps[history.cursor - 1];
    return !!coalesceKey && history.open && !!last && history.cursor === history.steps.length && last.coalesceKey === coalesceKey && at - last.at < UNDO_COALESCE_MS ? last : null;
}

function recordStep(history: DocHistory, step: HistoryStep): DocHistory {
    const last = history.steps[history.cursor - 1];
    const merge = mergeTarget(history, step.coalesceKey, step.at) !== null;
    let steps: HistoryStep[];
    if (merge) {
        // The merged step: the first step's inverse, the last one's ops.
        const merged: HistoryStep = { ...last, forward: compactDocOps([...last.forward, ...step.forward]), inverse: compactDocOps([...step.inverse, ...last.inverse]), at: step.at, builderFields: step.builderFields, after: step.after };
        steps = [...history.steps.slice(0, history.cursor - 1), merged];
    } else {
        steps = [...history.steps.slice(0, history.cursor), step];
    }
    while (steps.length > HISTORY_LIMIT) steps.shift();
    return { steps, cursor: steps.length, open: true };
}

/** Put `next` in place; the builder's copy follows unless the builder handed it over itself. */
function putDocument(get: (a: any) => any, set: Setter, next: FormDocument, builderFields?: StandardFormFieldDto[]) {
    const prev: FormDocument = get(formDocAtom);
    if (builderFields) {
        set(builderFieldsAtom, builderFields);
        rememberCopies(prev, next, builderFields);
    } else if (next.fields !== prev.fields) {
        set(builderFieldsAtom, builderCopy(next.fields));
    }
    if (next !== prev) set(formDocAtom, next);
}

const sameOps = (a: DocOp[], b: DocOp[]) => a.length === b.length && a.every((op, i) => op === b[i]);

export interface CommitMeta {
    label?: string;
    /** Typing under the same key within UNDO_COALESCE_MS is one step. */
    coalesceKey?: string;
    /** False: the change makes no undo step (loading, mount-time defaults). */
    undoable?: boolean;
}

function commitPlanned(get: (a: any) => any, set: Setter, change: PlannedChange, meta: CommitMeta, builderFields?: StandardFormFieldDto[]): boolean {
    const prev: FormDocument = get(formDocAtom);
    putDocument(get, set, change.doc, builderFields);
    if (change.doc === prev) return false;
    if (meta.undoable !== false) {
        // An inverse the engine would refuse (an uploaded image no longer on
        // the form, say) is recorded as an exact restore instead: undo must
        // never silently do nothing.
        // Typing that merges into the latest step and whose inverse that
        // step's own inverse covers needs no check: only the step's is kept.
        const history: DocHistory = get(docHistoryAtom);
        const at = Date.now();
        const target = mergeTarget(history, meta.coalesceKey, at);
        const covered = !!target && sameOps(compactDocOps([...change.inverse, ...target.inverse]), target.inverse);
        const inverse = covered || applyDocOps(change.doc, change.inverse, false).ok ? change.inverse : exactRestore(change.doc, prev);
        set(docHistoryAtom, recordStep(history, { forward: change.forward, inverse, label: meta.label, coalesceKey: meta.coalesceKey, at, builderFields, before: prev, after: change.doc }));
    }
    return true;
}

export interface DispatchArgs {
    ops: DocOp[];
    label?: string;
    coalesceKey?: string;
}

/**
 * Apply a batch of ops as one undo step (typing with the same coalesce key
 * within UNDO_COALESCE_MS extends the latest step). False when the batch was
 * refused (nothing changed).
 */
export const dispatchAtom = atom(null, (get, set, { ops, label, coalesceKey }: DispatchArgs) => {
    const doc = get(formDocAtom);
    const result = applyDocOps(doc, ops);
    if (!result.ok) return false;
    commitPlanned(get, set as Setter, { doc: result.doc, forward: ops, inverse: result.inverse }, { label, coalesceKey });
    return true;
});

function move(get: (a: any) => any, set: Setter, direction: 'undo' | 'redo'): boolean {
    const history: DocHistory = get(docHistoryAtom);
    const step = direction === 'undo' ? history.steps[history.cursor - 1] : history.steps[history.cursor];
    if (!step) return false;
    const current: FormDocument = get(formDocAtom);
    let result = applyDocOps(current, direction === 'undo' ? step.inverse : step.forward, false);
    // Ops that no longer apply: put the recorded document back exactly.
    if (!result.ok) result = applyDocOps(current, exactRestore(current, direction === 'undo' ? step.before : step.after), false);
    putDocument(get, set, result.doc);
    set(docHistoryAtom, { steps: history.steps, cursor: history.cursor + (direction === 'undo' ? -1 : 1), open: false });
    return true;
}

export const undoAtom = atom(null, (get, set) => move(get, set as Setter, 'undo'));
export const redoAtom = atom(null, (get, set) => move(get, set as Setter, 'redo'));

/**
 * Take in a whole form from elsewhere (an AI turn, a server copy) as the ops
 * that turn the current document into it: one undo step when `undoable`.
 * Form-level parts the form leaves out (or sends as null) are kept.
 */
export const applyRemoteAtom = atom(null, (get, set, serverForm: Partial<FormDocument>, options: { undoable?: boolean; label?: string } = {}) => {
    const doc = get(formDocAtom);
    rememberStorageImageUrls(formImageUrls(serverForm as FormDocument));
    let change = Array.isArray(serverForm?.fields) ? planFields(doc, serverForm.fields) : noChange(doc);
    const values: Partial<Record<FormStateKey, unknown>> = {};
    for (const key of FORM_STATE_KEYS) {
        const value = (serverForm as Record<string, unknown>)?.[key];
        if (value !== undefined && (value !== null || key === 'description')) values[key] = value;
    }
    if (Object.keys(values).length) change = chain(change, planFormKeys(change.doc, values));
    return commitPlanned(get, set as Setter, change, { label: options.label ?? 'Remote change', undoable: options.undoable !== false });
});

/** Load a form: the document becomes a copy of it, and undo history starts over. */
export const resetFromServerAtom = atom(null, (get, set, form: Partial<FormDocument>) => {
    const doc = { ...clone(form), fields: clone(form?.fields ?? []) } as FormDocument;
    // What the server sent is first-party.
    rememberStorageImageUrls(formImageUrls(doc));
    set(formDocAtom, doc);
    set(builderFieldsAtom, builderCopy(doc.fields));
    set(docHistoryAtom, emptyHistory());
    resetListeners.forEach((listener) => listener());
});

// ---------------------------------------------------------------------------
// Compatibility: the older mutators and the form state
// ---------------------------------------------------------------------------

/**
 * The builder handed over its pages (`setFormFields`): what changed becomes
 * one undo step of ops; the handed-over array stays the builder's copy.
 */
export const commitBuilderFieldsAtom = atom(null, (get, set, fields: StandardFormFieldDto[], coalesceKey?: string) => {
    const doc = get(formDocAtom);
    return commitPlanned(get, set as Setter, planFields(doc, fields), { coalesceKey }, fields);
});

/** Seed the pages and start undo history over (the form-level parts stay). */
export const initBuilderFieldsAtom = atom(null, (get, set, fields: StandardFormFieldDto[]) => {
    const prev = get(formDocAtom);
    const doc = { ...prev, fields: clone(fields) ?? [] };
    rememberStorageImageUrls(formImageUrls(doc));
    set(formDocAtom, doc);
    set(builderFieldsAtom, fields);
    rememberCopies(prev, doc, fields ?? []);
    set(docHistoryAtom, emptyHistory());
    resetListeners.forEach((listener) => listener());
});

/** Form-level values written by the form state: one undo step (unless `undoable` is false). */
export const commitFormKeysAtom = atom(null, (get, set, values: Partial<Record<FormStateKey, unknown>>, meta: CommitMeta = {}) => {
    const doc = get(formDocAtom);
    return commitPlanned(get, set as Setter, planFormKeys(doc, values), meta);
});

/**
 * Undo one step, but only while the latest step is still `after`: the step
 * itself (see latestStep), or — older callers — the pages it left, as
 * serialised right when it was made. An undo toast must not undo some later
 * edit instead. True when it undid.
 */
export const undoIfLatestAtom = atom(null, (get, set, after: HistoryStep | string | null) => {
    const history = get(docHistoryAtom);
    if (!after || history.cursor <= 0 || history.cursor !== history.steps.length) return false;
    const step = history.steps[history.cursor - 1];
    if (typeof after === 'string' ? JSON.stringify(step.builderFields ?? get(builderFieldsAtom)) !== after : step !== after) return false;
    return move(get, set as Setter, 'undo');
});

/** The latest undo step (null when there is none): what an undo toast hands back to undoIfLatestAtom. */
export function latestStep(history: DocHistory): HistoryStep | null {
    return history.cursor > 0 ? history.steps[history.cursor - 1] : null;
}
