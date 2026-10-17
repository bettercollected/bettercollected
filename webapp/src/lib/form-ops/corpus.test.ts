/**
 * The shared conformance corpus of the edit operations
 * (docs/spec/form-ops-v1.cases.json, format in docs/spec/README.md): each
 * case applies its operations to its form with this engine and must give the
 * expected form or error — the same cases the backend's engine passes.
 * Skipped when the corpus is not there.
 */
import { existsSync, readFileSync } from 'fs';
import { resolve } from 'path';

import { describe, expect, it } from 'vitest';

import { applyOps } from './apply';
import type { FormDoc, FormOp } from './types';

const CORPUS = resolve(__dirname, '../../../../docs/spec/form-ops-v1.cases.json');
const corpus = existsSync(CORPUS) ? JSON.parse(readFileSync(CORPUS, 'utf8')) : null;
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;

/** A `{"$generated": {pages, fieldsPerPage}}` form: pages `p<i>` with short text questions `p<i>f<j>` titled "Q". */
function generated(spec: { pages: number; fieldsPerPage: number }): FormDoc {
    return {
        title: 'Generated',
        builderVersion: 'v2',
        fields: Array.from({ length: spec.pages }, (_, p) => ({
            id: `p${p}`,
            index: p,
            type: 'slide',
            properties: { fields: Array.from({ length: spec.fieldsPerPage }, (_, f) => ({ id: `p${p}f${f}`, index: f, type: 'short_text', title: 'Q' })) }
        }))
    } as FormDoc;
}

function formOf(before: any): FormDoc {
    const document = typeof before === 'string' ? corpus.forms[before] : before;
    return document.$generated ? generated(document.$generated) : JSON.parse(JSON.stringify(document));
}

/**
 * What a document reads as: no null entries, no empty objects (the backend
 * sends neither back), keys sorted, and generated uuids named `$uuid:<n>` in
 * order of first appearance, depth first.
 */
function normalised(document: unknown): unknown {
    const names = new Map<string, string>();
    const walk = (value: any): any => {
        if (Array.isArray(value)) return value.map(walk);
        if (value && typeof value === 'object') {
            const out: Record<string, any> = {};
            for (const key of Object.keys(value).sort()) {
                const item = walk(value[key]);
                if (item === null || item === undefined) continue;
                if (typeof item === 'object' && !Array.isArray(item) && !Object.keys(item).length) continue;
                out[key] = item;
            }
            return out;
        }
        if (typeof value === 'string' && UUID.test(value)) {
            if (!names.has(value)) names.set(value, `$uuid:${names.size + 1}`);
            return names.get(value);
        }
        return value;
    };
    return walk(document);
}

describe.skipIf(!corpus)('form ops conformance corpus', () => {
    const cases: any[] = corpus?.cases ?? [];

    it.each(cases.map((c) => [c.name, c]))('%s', (_name, c: any) => {
        const before = formOf(c.before);
        const { doc, results } = applyOps(before, c.ops as FormOp[], { atomic: c.atomic, applySettings: false, skipInverse: true });
        const after = normalised(doc);
        const error = c.expect.error;
        if (!error) {
            expect(results.filter((r) => !r.ok).map((r) => `#${r.index} ${r.op}: ${r.message}`)).toEqual([]);
        } else {
            expect(
                results
                    .slice(0, error.index)
                    .filter((r) => !r.ok)
                    .map((r) => r.message)
            ).toEqual([]);
            expect(results[error.index]?.ok, results[error.index]?.message).toBe(false);
            expect(results[error.index].message).toContain(error.messageContains);
            if (c.atomic) expect(after).toEqual(normalised(before));
        }
        if ('form' in c.expect) expect(after).toEqual(normalised(c.expect.form));
    });
});
