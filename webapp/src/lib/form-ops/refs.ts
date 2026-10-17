/**
 * Client references: an op that creates a page, question or group may name it
 * with `ref`; later ops of the same batch use `"$ref:<name>"` wherever a page
 * or question id is expected (REF_ID_KEYS), logic conditions and page jumps
 * included. Backend twin: `_refs_defined`, `_resolve_refs`, `ref_dependencies`.
 */
import { OpError, REF_ID_KEYS, REF_PATTERN, REF_PREFIX } from './model';
import type { FormOp } from './types';

/** ref name -> [index of the op that defines it, the created id or null when that op failed]. */
export type RefTable = Map<string, [number, string | null]>;

/** `[name, position]` of each ref an op defines: its own (position null) and those of the questions it creates with it. */
export function refsDefined(op: FormOp): Array<[string, number | null]> {
    const defined: Array<[string, number | null]> = [];
    const check = (name: string) => {
        if (!REF_PATTERN.test(name)) throw new OpError(`String should match pattern '${REF_PATTERN.source}'`);
        return name;
    };
    if (op.op === 'add_field') {
        if (op.ref && op.field?.ref && op.ref !== op.field.ref) throw new OpError('add_field has two different refs: give one, on the op or on its field.');
        const name = op.ref || op.field?.ref;
        if (name) defined.push([check(name), null]);
        return defined;
    }
    const own = (op as { ref?: string | null }).ref;
    if (own) defined.push([check(own), null]);
    if (op.op === 'add_page' || op.op === 'add_group') {
        (op.fields ?? []).forEach((spec, i) => {
            if (spec.ref) defined.push([check(spec.ref), i]);
        });
    }
    return defined;
}

function refTarget(name: string, refs: RefTable): string {
    const entry = refs.get(name);
    if (!entry) {
        throw new OpError(`Unknown reference '${REF_PREFIX}${name}': no earlier operation in this batch defines the ref '${name}' (refs are set with "ref" on add_page, add_field, add_group or duplicate_page, or on a field inside add_page or add_group).`);
    }
    const [index, created] = entry;
    if (created === null) throw new OpError(`'${REF_PREFIX}${name}' names what operation #${index} would have created, but that operation failed.`);
    return created;
}

function* usedRefs(value: any, key?: string): Generator<string> {
    if (Array.isArray(value)) {
        for (const item of value) yield* usedRefs(item);
    } else if (value && typeof value === 'object') {
        for (const [k, v] of Object.entries(value)) yield* usedRefs(v, k);
    } else if (key !== undefined && REF_ID_KEYS.has(key) && typeof value === 'string' && value.startsWith(REF_PREFIX)) {
        yield value.slice(REF_PREFIX.length);
    }
}

/** `op` with every `"$ref:<name>"` under an id key replaced by the id it names (the same object when it uses none). */
export function resolveRefs<T extends FormOp>(op: T, refs: RefTable): T {
    if (usedRefs(op).next().done) return op;
    const walk = (value: any, key?: string): any => {
        if (Array.isArray(value)) return value.map((v) => walk(v));
        if (value && typeof value === 'object') return Object.fromEntries(Object.entries(value).map(([k, v]) => [k, walk(v, k)]));
        if (key !== undefined && REF_ID_KEYS.has(key) && typeof value === 'string' && value.startsWith(REF_PREFIX)) return refTarget(value.slice(REF_PREFIX.length), refs);
        return value;
    };
    return walk(op);
}

/**
 * For each op, the indexes of the earlier ops whose refs it uses: accepting
 * the op without them cannot work. A ref nobody defines is left to the
 * engine to report.
 */
export function refDependencies(ops: FormOp[]): Array<Set<number>> {
    const definers = new Map<string, number>();
    return ops.map((op, i) => {
        const needs = new Set<number>();
        for (const name of usedRefs(op)) if (definers.has(name)) needs.add(definers.get(name)!);
        let defined: Array<[string, number | null]> = [];
        try {
            defined = refsDefined(op);
        } catch {
            defined = [];
        }
        for (const [name] of defined) if (!definers.has(name)) definers.set(name, i);
        return needs;
    });
}
