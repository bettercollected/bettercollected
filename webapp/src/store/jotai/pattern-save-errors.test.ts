import { describe, expect, it } from 'vitest';

import { patternSaveErrorsOf } from './pattern-save-errors';

const body = JSON.stringify({
    fields: [
        {
            id: 'page',
            properties: {
                fields: [
                    { id: 'q-1', validations: { regex: '^(a+)+$' } },
                    { id: 'q-2', validations: {} }
                ]
            }
        }
    ]
});
const refusal = (errors: unknown) => ({ error: { status: 422, data: { code: 'unsafe_pattern', message: 'm', errors } } });

describe('patternSaveErrorsOf', () => {
    it('reads the refused patterns by question id, as sent', () => {
        expect(patternSaveErrorsOf(refusal([{ fieldId: 'q-1', hazard: 'nested_repeat' }]), body)).toEqual({ 'q-1': { hazard: 'nested_repeat', regex: '^(a+)+$' } });
    });

    it('ignores other failures, unknown hazards and questions that were not sent', () => {
        expect(patternSaveErrorsOf({ error: { status: 422, data: { code: 'image_not_allowed' } } }, body)).toBeNull();
        expect(patternSaveErrorsOf({ error: { status: 500 } }, body)).toBeNull();
        expect(patternSaveErrorsOf({ data: {} }, body)).toBeNull();
        expect(
            patternSaveErrorsOf(
                refusal([
                    { fieldId: 'q-1', hazard: 'made_up' },
                    { fieldId: 'q-9', hazard: 'backreference' }
                ]),
                body
            )
        ).toEqual({});
        expect(patternSaveErrorsOf(refusal([{ fieldId: 'q-1', hazard: 'nested_repeat' }]), 'not json')).toBeNull();
    });
});
