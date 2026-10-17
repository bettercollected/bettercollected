import React from 'react';

import { render } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import FormRenderer from '@app/components/form/form-renderer';

const seen: { ids?: string[] } = {};
vi.mock('@app/components/modal-views/full-screen-modals/view-response-full-modal-view', () => ({
    IndividualFormResponse: ({ formFields }: { formFields: Array<{ id: string }> }) => {
        seen.ids = formFields.map((field) => field.id);
        return null;
    }
}));

describe("the respondent's own submission view", () => {
    it('leaves out calculations kept from respondents', () => {
        const form = {
            builderVersion: 'v2',
            fields: [
                {
                    id: 'p',
                    index: 0,
                    type: 'slide',
                    properties: {
                        fields: [
                            { id: 'qty', index: 0, type: 'number', title: 'Quantity' },
                            { id: 'total', index: 1, type: 'calculated', title: 'Total', properties: { expression: 1 } },
                            { id: 'risk', index: 2, type: 'calculated', title: 'Risk', properties: { expression: 2, hiddenFromRespondents: true } }
                        ]
                    }
                }
            ]
        };
        render(<FormRenderer form={form} response={{ answers: {} }} />);
        expect(seen.ids).toEqual(['qty', 'total']);
    });
});
