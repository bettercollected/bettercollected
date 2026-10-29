// Answer patterns a backtracking browser must not be handed (utils/pattern-safety.ts).
// The cases are shared with the server (common/tests/test_pattern_safety.py,
// docs/spec/pattern-safety.cases.json). The check looks at the shape of the
// pattern only, so nothing here runs a pattern against a text.
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

import { PATTERN_HAZARDS, PATTERN_HAZARD_MESSAGES, patternHazard } from '@app/utils/pattern-safety';

const cases = JSON.parse(readFileSync(resolve(__dirname, '../../../docs/spec/pattern-safety.cases.json'), 'utf-8')) as { safe: string[]; unsafe: Array<{ pattern: string; hazard: string }> };

describe('patternHazard', () => {
    it.each(cases.safe)('accepts %s', (pattern) => {
        expect(patternHazard(pattern)).toBeNull();
    });

    it.each(cases.unsafe.map((c) => [c.pattern.slice(0, 40), c.pattern, c.hazard]))('refuses %s', (_label, pattern, hazard) => {
        expect(patternHazard(pattern)).toBe(hazard);
    });

    it('has a case for every hazard and a message for each', () => {
        expect(new Set(cases.unsafe.map((c) => c.hazard))).toEqual(new Set(PATTERN_HAZARDS));
        expect(Object.keys(PATTERN_HAZARD_MESSAGES).sort()).toEqual([...PATTERN_HAZARDS].sort());
    });

    it('has no hazard in no pattern', () => {
        expect(patternHazard(undefined)).toBeNull();
        expect(patternHazard(null)).toBeNull();
        expect(patternHazard('')).toBeNull();
    });
});
