import { describe, expect, it } from 'vitest';

import { getFlowSessionId, resetFlowSession } from './flow-session';

describe('flow-session — anonymous per-form session ids', () => {
    it('is stable for a form within a page load', () => {
        const a = getFlowSessionId('form-a');
        expect(getFlowSessionId('form-a')).toBe(a);
    });

    it('differs between forms', () => {
        expect(getFlowSessionId('form-a')).not.toBe(getFlowSessionId('form-b'));
    });

    it('reset yields a fresh attempt', () => {
        const before = getFlowSessionId('form-c');
        resetFlowSession('form-c');
        expect(getFlowSessionId('form-c')).not.toBe(before);
    });

    it('looks like a uuid — random, nothing derivable about the responder', () => {
        expect(getFlowSessionId('form-d')).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/);
    });
});
