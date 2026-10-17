/**
 * The ops engine: apply a batch of form ops to a form document.
 *
 * TypeScript twin of `apply_form_ops` (backend/app/services/ai/ops.py): the
 * same ops, the same checks, the same result messages, client references,
 * size limits and atomic/partial semantics. Differences are noted where they
 * are made.
 *
 * Documents are immutable: every op is applied with immer, along the path of
 * what it changes only, so unchanged pages and questions keep their
 * references (cheap equality checks, cheap undo).
 */
import { Immer } from 'immer';
import { v4 as uuidv4 } from 'uuid';

import { calculationsTouched, newCalculationProblem } from './calculations';
import { dateRuleFixes } from './date-rules';
import { EDITOR_ONLY_OPS, HANDLERS } from './handlers';
import { DROPPED_HIDDEN_REFERENCES_MARK, DROPPED_REFERENCES_MARK, DROPPED_RULES_MARK, type OpContext, draftAt, droppedRulesText, setKey } from './handlers/context';
import { editorGrowth } from './handlers/editor';
import { buildInverse, touchedEntities } from './inverse';
import { MAX_OPS_PER_BATCH, OpError, SIZE_LIMIT_SKIPPED, SizeLimitReached, countFields, findPage, formSize, hasOwn, isRepeatingGroup, isSlide, sizeProblem } from './model';
import { referenceFixes } from './references';
import { type RefTable, refsDefined, resolveRefs } from './refs';
import type { ApplyOptions, ApplyResult, FormDoc, FormField, FormOp, OpResult } from './types';

// Own instance, so that its settings are the engine's alone. Results are
// frozen: documents are immutable by contract, and immer skips frozen
// subtrees when it finishes a draft, which keeps large forms fast.
export const immer = new Immer({ autoFreeze: true });

/** The plain refusal for a batch over MAX_OPS_PER_BATCH, or null (backend `too_many_ops`). */
export function tooManyOps(count: number): string | null {
    if (count <= MAX_OPS_PER_BATCH) return null;
    return `At most ${MAX_OPS_PER_BATCH} operations can be sent at once (this batch has ${count}); split them into several batches.`;
}

/** Pages and fields an op adds, known before it runs (backend `_growth`). */
function growth(doc: FormDoc, op: FormOp): [number, number] {
    switch (op.op) {
        case 'add_page':
            return [1, op.fields?.length ?? 0];
        case 'add_field':
            return [0, 1];
        case 'add_group':
            return [0, 1 + (op.fields?.length ?? 0)];
        case 'duplicate_page':
            return [1, countFields(findPage(doc, op.pageId).page.properties?.fields as FormField[] | undefined)];
        case 'insert_field':
        case 'insert_page':
        case 'replace_field':
            return editorGrowth(doc, op);
        default:
            return [0, 0];
    }
}

const STRUCTURAL = new Set(['add_field', 'add_group', 'remove_field', 'move_field', 'add_page', 'remove_page', 'duplicate_page', 'insert_field', 'replace_field', 'insert_page']);

/**
 * Ops that can leave a date rule dangling: they change which questions
 * exist, where they are, their type or whether they are internal.
 */
function mayStrandDateRules(op: FormOp): boolean {
    return STRUCTURAL.has(op.op) || (op.op === 'update_field' && (op.patch?.internal != null || op.patch?.dateRules != null));
}

/**
 * The document as a batch leaves it (backend `finished_form`): renumbered,
 * and without the date rules a save would refuse. Only what is off is
 * written, so a document already in order comes back as is.
 *
 * With `base` (the document the batch started from, itself finished), pages
 * the batch left alone are not looked into, and `sweepRules` false skips the
 * date rules (no op of the batch could strand one).
 */
export function finishDoc(doc: FormDoc, base?: FormDoc, sweepRules = true): FormDoc {
    const renumber: Array<[number[], number]> = [];
    let slideIndex = 0;
    const unchanged = new Set(base ? (base.fields ?? []) : []);
    (doc.fields ?? []).forEach((page, pagePos) => {
        if (!isSlide(page)) return;
        if (page.index !== slideIndex) renumber.push([[pagePos], slideIndex]);
        slideIndex++;
        if (unchanged.has(page)) return;
        ((page.properties?.fields as FormField[] | undefined) ?? []).forEach((field, fieldPos) => {
            if (field.index !== fieldPos) renumber.push([[pagePos, fieldPos], fieldPos]);
            if (isRepeatingGroup(field)) {
                ((field.properties?.fields as FormField[] | undefined) ?? []).forEach((child, childPos) => {
                    if (child.index !== childPos) renumber.push([[pagePos, fieldPos, childPos], childPos]);
                });
            }
        });
    });
    const fixes = sweepRules ? dateRuleFixes(doc.fields as FormField[]) : [];
    if (!renumber.length && !fixes.length) return doc;
    return immer.produce(doc, (draft) => {
        for (const [path, index] of renumber) draftAt(draft, path).index = index;
        for (const fix of fixes) setKey(draftAt(draft, fix.path).properties, 'dateRules', fix.rules);
    });
}

/**
 * Do what an op's message marks for after its draft is finished (dropping
 * dangling date rules and references, see handlers/context.ts) and put the
 * notes in place of the marks.
 */
function settleMarks(doc: FormDoc, message: string, ctx: OpContext | null): [FormDoc, string] {
    let next = doc;
    let text = message;
    if (text.includes(DROPPED_RULES_MARK)) {
        const fixes = dateRuleFixes(next.fields as FormField[]);
        if (fixes.length) {
            next = immer.produce(next, (draft) => {
                for (const fix of fixes) setKey(draftAt(draft, fix.path).properties, 'dateRules', fix.rules);
            });
        }
        text = text.replace(DROPPED_RULES_MARK, droppedRulesText(fixes.reduce((sum, fix) => sum + fix.dropped, 0)));
    }
    const hidden = text.includes(DROPPED_HIDDEN_REFERENCES_MARK);
    if (hidden || text.includes(DROPPED_REFERENCES_MARK)) {
        const { fixes, removed } = referenceFixes(next, { gone: ctx?.referencesGone, hiddenNames: hidden ? new Set(next.hiddenFields ?? []) : undefined, hiddenGone: ctx?.hiddenGone });
        if (fixes.length) {
            next = immer.produce(next, (draft) => {
                for (const fix of fixes) {
                    const target: any = draftAt(draft, fix.path);
                    if (fix.title) target.title = fix.title.value;
                    if (fix.logic) setKey(target.properties, 'logic', fix.logic.value);
                    if (fix.jumps) setKey(target.properties, 'jumps', fix.jumps.value);
                }
            });
        }
        text = hidden ? text.replace(DROPPED_HIDDEN_REFERENCES_MARK, removed ? ` (and ${removed} piping reference(s) to removed ones)` : '') : text.replace(DROPPED_REFERENCES_MARK, removed ? ` (and ${removed} logic or piping reference(s) to it)` : '');
    }
    return [next, text];
}

const emptyResult = (doc: FormDoc, results: OpResult[]): ApplyResult => ({ doc, results, createdIds: [], inverse: [], touched: { pages: new Set(), fields: new Set(), form: new Set() } });

/**
 * Apply `ops` to `doc`; `doc` itself is never changed.
 *
 * Partial (default): failed ops are reported and skipped. As in the backend,
 * an op that fails part-way keeps the changes it made before failing (its
 * result still says it failed). Atomic: when any op fails, `doc` comes back
 * unchanged; every op is still tried so that all errors are reported.
 *
 * Size: an op that would take the form past MAX_PAGES or MAX_FIELDS fails
 * before it runs, and the rest of the batch is not applied; when an op got
 * there unforeseen, nothing of the batch is applied.
 */
export function applyOps(doc: FormDoc, ops: FormOp[], options: ApplyOptions = {}): ApplyResult {
    const newId = options.newId ?? (() => uuidv4());
    let working = doc;
    const results: OpResult[] = [];
    const createdIds: string[] = [];
    let size = formSize(working);
    let stopped = false;
    const refs: RefTable = new Map();

    for (let i = 0; i < ops.length; i++) {
        const raw = ops[i];
        const name = String(raw?.op);
        if (stopped) {
            results.push({ index: i, op: name, ok: false, message: SIZE_LIMIT_SKIPPED });
            continue;
        }
        const handler = hasOwn(HANDLERS, name) ? (HANDLERS as Record<string, (ctx: OpContext, op: any) => string>)[name] : undefined;
        let created: [string, string[]] | null = null;
        let defined: Array<[string, number | null]> = [];
        try {
            if (!handler) throw new OpError(`Unknown operation '${name}'.`);
            if (options.editor === false && EDITOR_ONLY_OPS.has(name)) throw new OpError(`The operation '${name}' is only available in the form editor; it cannot be used here.`);
            defined = refsDefined(raw);
            const names = defined.map(([n]) => n);
            for (const n of names) {
                if (names.filter((m) => m === n).length > 1) throw new OpError(`The ref '${n}' is defined twice in this operation.`);
                if (refs.has(n)) throw new OpError(`The ref '${n}' is already defined by operation #${refs.get(n)![0]}; each ref names one new item.`);
            }
            const op = resolveRefs(raw, refs);
            const [addPages, addFields] = growth(working, op);
            if (addPages || addFields) {
                const problem = sizeProblem(size[0] + addPages, size[1] + addFields, size);
                if (problem) throw new SizeLimitReached(problem);
            }
            let message = '';
            let failure: OpError | null = null;
            const state = working;
            let opContext: OpContext | null = null;
            working = immer.produce(state, (draft) => {
                const ctx: OpContext = { state, draft, newId, options, noteCreated: (id, nested = []) => (created = [id, nested]) };
                opContext = ctx;
                try {
                    message = handler(ctx, op);
                } catch (error) {
                    if (error instanceof OpError) failure = error;
                    else throw error;
                }
            });
            if (failure) throw failure;
            [working, message] = settleMarks(working, message, opContext);
            // Calculations stay valid after every op (backend apply_form_ops):
            // one left broken refuses the op and undoes it.
            if (calculationsTouched(state, working)) {
                const problem = newCalculationProblem(state, working);
                if (problem) {
                    working = state;
                    throw new OpError(problem);
                }
            }
            if (STRUCTURAL.has(name)) {
                const after = formSize(working);
                const problem = sizeProblem(after[0], after[1], size);
                // Not foreseen by growth(): the change is made, so nothing of this batch may be applied.
                if (problem) throw new SizeLimitReached(problem);
                size = after;
            }
            const made = created as [string, string[]] | null;
            if (made) {
                createdIds.push(made[0], ...made[1]);
                for (const [n, position] of defined) refs.set(n, [i, position === null ? made[0] : made[1][position]]);
            }
            results.push({ index: i, op: name, ok: true, message, ...(made ? { createdId: made[0] } : {}) });
        } catch (error) {
            if (!(error instanceof OpError)) throw error;
            // Later uses of this op's refs then say that it failed.
            for (const [n] of defined) if (!refs.has(n)) refs.set(n, [i, null]);
            results.push({ index: i, op: name, ok: false, message: error.message });
            if (error instanceof SizeLimitReached) {
                stopped = true;
                const now = formSize(working);
                if (now[0] !== size[0] || now[1] !== size[1]) {
                    // changed past the limit: drop the whole batch
                    for (let j = i + 1; j < ops.length; j++) results.push({ index: j, op: String(ops[j]?.op), ok: false, message: SIZE_LIMIT_SKIPPED });
                    return emptyResult(doc, results);
                }
            }
        }
    }

    if (options.atomic && !results.every((r) => r.ok)) return emptyResult(doc, results);
    const finished = finishDoc(
        working,
        doc,
        ops.some((op, i) => results[i].ok && mayStrandDateRules(op))
    );
    if (finished === doc) return emptyResult(doc, results);
    return {
        doc: finished,
        results,
        createdIds: results.some((r) => r.ok) ? createdIds : [],
        inverse: options.skipInverse ? [] : buildInverse(doc, finished),
        touched: touchedEntities(doc, finished)
    };
}

/** Did a batch change the form? Partial: when any op applied. Atomic: only when every op did. */
export function applied(results: OpResult[], atomic: boolean): boolean {
    if (atomic) return results.length > 0 && results.every((r) => r.ok);
    return results.some((r) => r.ok);
}
