import { describe, expect, it } from 'vitest';

import { applyOps } from './apply';
import type { FormDoc, FormOp } from './types';

const base = (): FormDoc => ({ title: 'T', builderVersion: 'v2', fields: [{ id: 'p1', index: 0, type: 'slide', properties: { fields: [] } }] }) as unknown as FormDoc;
const insert = (validations: Record<string, unknown>) => ({ op: 'insert_field', pageId: 'p1', index: 0, field: { id: 'g', type: 'tags', title: 'Topics', validations } }) as FormOp;
const run = (op: FormOp) => applyOps(base(), [op], { atomic: true, skipInverse: true }).results[0];

describe('the limits of a tags question in a whole question the builder sends (the same as the server)', () => {
    it.each([
        [{ maxChoices: 0 }, 'The most tags is between 1 and 30.'],
        [{ maxChoices: 31 }, 'The most tags is between 1 and 30.'],
        [{ minChoices: 31 }, 'The fewest tags is between 0 and 30.'],
        [{ minChoices: 5, maxChoices: 3 }, 'The fewest tags is more than the most.'],
        [{ maxLength: 0 }, 'The length of a tag is between 1 and 40 characters.'],
        [{ maxLength: 999 }, 'The length of a tag is between 1 and 40 characters.']
    ])('refuses %j', (validations, message) => {
        const result = run(insert(validations));
        expect(result.ok).toBe(false);
        expect(result.message).toContain(message);
    });

    it('takes limits within the caps', () => {
        for (const validations of [{ minChoices: 0 }, { maxChoices: 30, maxLength: 40 }, { minChoices: 3, maxChoices: 3 }, { maxLength: 1 }]) expect(run(insert(validations)).ok).toBe(true);
    });
});
