import { describe, expect, it } from 'vitest';

import { idMaker, smallForm } from './__fixtures__/forms';
import { applyOps } from './apply';
import type { FormOp } from './types';

/**
 * Names that come from a payload (node, mark and attribute types, op names)
 * are looked up as own keys only: `constructor`, `__proto__` and the like
 * must never match what every object inherits.
 */
const run = (ops: any[]) => applyOps(smallForm(), ops as FormOp[], { atomic: false, newId: idMaker() });
// JSON.parse keeps "__proto__" as an own key, as a request body would
const titled = (title: string) => JSON.parse(`{"op":"update_field","fieldId":"name","patch":{"title":${title}}}`);

describe('names from a payload never match inherited properties', () => {
    it.each(['constructor', '__proto__', 'toString', 'hasOwnProperty'])('refuses a node of type %s', (type) => {
        const { results } = run([titled(`{"type":"doc","content":[{"type":"${type}"}]}`)]);
        expect(results[0].ok).toBe(false);
        expect(results[0].message).toBe(`A rich-text title cannot hold a '${type}' node.`);
    });

    it.each(['constructor', '__proto__'])('refuses a mark of type %s', (type) => {
        const { results } = run([titled(`{"type":"doc","content":[{"type":"text","text":"x","marks":[{"type":"${type}"}]}]}`)]);
        expect(results[0].message).toBe(`A rich-text title cannot use a '${type}' mark.`);
    });

    it.each(['constructor', '__proto__'])('refuses an attribute named %s', (key) => {
        const { results } = run([titled(`{"type":"doc","content":[{"type":"paragraph","attrs":{"${key}":"x"}}]}`)]);
        expect(results[0].message).toBe(`A 'paragraph' cannot have the attribute '${key}'.`);
    });

    it.each(['constructor', '__proto__', 'toString'])('reports an op named %s as unknown', (name) => {
        const { results } = run([JSON.parse(`{"op":"${name}"}`)]);
        expect(results[0].message).toBe(`Unknown operation '${name}'.`);
    });
});
